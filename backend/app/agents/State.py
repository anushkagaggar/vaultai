"""
VaultAI V3 — agents/state.py
=============================
The single source of truth for graph state.

Every LangGraph node receives a VaultAIState and returns a partial
VaultAIState. No node may invent fields. No node may rename fields.
If this file changes shape, every node that reads or writes that field
must be updated before the graph can compile.

Design decisions recorded here so future engineers understand the why:

1.  IMMUTABLE INPUT FIELDS (user_id, user_message, request_params)
    Set once at graph entry by the FastAPI route. Never written by any node.
    Nodes read them; the router classifies from them. They do not change.

2.  ROUTING FIELD (plan_type)
    Written once by intent_classifier. All conditional edges downstream
    read this field. It must be a PlanType enum value or None (pre-routing).
    COMBINED is a valid plan_type — it triggers all three subgraphs.

3.  V2 DATA FIELDS (v2_analytics, v2_expenses)
    Loaded by the first node in each agent subgraph (budget_load_v2,
    invest_fetch_data, goal_define). They are read-only after that point.
    These fields are the bridge between V2 (the existing insight engine)
    and V3 (the planning layer). V3 never re-computes V2 analytics.

4.  DETERMINISTIC OUTPUT FIELDS (projected_outcomes, assumptions, constraints)
    Written ONLY by simulation nodes (budget_optimize, invest_allocate,
    goal_simulate, sim_run). The LLM explanation nodes may READ these fields
    to narrate them but must NEVER WRITE to them. The validation checkpoint
    re-runs the simulation and asserts these match.

5.  EXTERNAL DATA FIELDS (external_data, external_freshness)
    Written by invest_fetch_data only. external_freshness carries the
    data quality signal ("live" | "cached" | "fallback") that propagates
    to the plan's confidence block and is shown in the UI.

6.  VALIDATION FIELDS (validation_status, validation_errors)
    Written by checkpoint nodes only. The conditional edge after each
    checkpoint reads validation_status to decide: proceed to LLM explain
    OR route to fallback. Never written by LLM nodes.

7.  LLM OUTPUT FIELDS (llm_explanation, explanation_filtered)
    llm_explanation: raw output from the LLM explain node.
    explanation_filtered: output after llm_output_filter.py scrubs
    speculative language and unvalidated numbers. Only explanation_filtered
    is ever stored to the DB or returned to the user.
    RULE: These fields are NEVER the source of any numeric value.

8.  GRAPH TRACE (graph_trace)
    Appended to by every node as it executes. This is the list that
    GraphExecutionTrace.tsx renders to the user. It answers: "what did
    VaultAI actually run to produce this plan?" Starts as empty list.
    NOTE: The spec's VaultAIState does not include this field, but the
    Plan Output Schema requires graph_trace in the stored plan. Adding
    it to state here means plan_persist can write it directly — no
    reconstruction needed after the graph finishes.

9.  SOURCE HASH (source_hash)
    sha256(expense_ids + request_params + pipeline_version). Computed
    by plan_persist before the DB write. Enables idempotent re-runs:
    if the same hash already exists in the plans table, return the
    existing plan rather than recomputing. Also written to audit_payload.
    NOTE: Same rationale as graph_trace — not in spec's TypedDict but
    required by the plan output schema and computed inside the graph.

10. FINAL FIELDS (plan_id, confidence, degraded, audit_payload)
    Written by plan_persist as the last node in every path.
    degraded: True if any checkpoint routed to fallback OR if external
    data was unavailable. This flag is shown prominently in the UI so
    users know the plan ran in reduced-confidence mode.

RULE FOR ALL NODES:
    Return only the keys you actually changed:
        return {**state, "validation_status": ValidationStatus.PASSED}
    Never return the full state wholesale if you only changed one field.
    This makes node behaviour auditable and prevents accidental overwrites.

Author: VaultAI V3
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlanType(str, Enum):
    """
    What kind of plan is being generated.

    Set by intent_classifier. Drives all conditional edges in the graph.
    COMBINED triggers all three agent subgraphs in sequence.
    UNKNOWN means the router could not classify — routes to clarify node.
    """
    BUDGET   = "budget"
    INVEST   = "invest"
    GOAL     = "goal"
    SIMULATE = "simulate"
    COMBINED = "combined"   # all 3 subgraphs — Phase 5
    UNKNOWN  = "unknown"    # routes to clarify node


class ValidationStatus(str, Enum):
    """
    Result of a checkpoint node's re-run assertion.

    PASSED:   simulation re-run matched stored projected_outcomes exactly.
              Graph proceeds to LLM explain node.
    FAILED:   mismatch detected. Graph routes to fallback node.
              LLM explain node is SKIPPED entirely.
    FALLBACK: LLM explain node timed out or produced unvalidatable output.
              Deterministic summary is used instead.
    """
    PASSED   = "passed"
    FAILED   = "failed"
    FALLBACK = "fallback"


class ExternalFreshness(str, Enum):
    """
    Quality signal for external market data.

    Written by invest_fetch_data. Read by plan_persist when computing
    the confidence block. Shown in the UI as a data quality indicator.
    """
    LIVE     = "live"      # fetched successfully in this request
    CACHED   = "cached"    # served from TTL cache (< 24h for equity, < 7d for macro)
    FALLBACK = "fallback"  # API unavailable — hardcoded fallback rates used


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class VaultAIState(TypedDict):
    """
    The complete state contract for the VaultAI V3 LangGraph agent system.

    Every field is documented with:
      - Who writes it
      - Who reads it
      - What happens if it's None

    Fields are grouped by lifecycle stage so the flow is readable top-to-bottom.
    """

    # ── IMMUTABLE INPUT ──────────────────────────────────────────────────────
    # Set by the FastAPI route before graph.invoke(). Never written by nodes.

    user_id: str
    """
    Authenticated user ID from JWT. Propagated to every DB query and
    every Qdrant vector filter to enforce strict user isolation.
    Written by: FastAPI route (pre-graph).
    Read by: all nodes that touch DB or vector store.
    """

    user_message: str
    """
    The raw natural language input from the user.
    Written by: FastAPI route (pre-graph).
    Read by: intent_classifier (classification), explain nodes (context).
    """

    request_params: dict
    """
    Structured parameters extracted from the API request body.
    For /plans/budget: {income_monthly, expense_categories, savings_target}
    For /plans/invest: {risk_profile, investment_amount, horizon_months}
    For /plans/goal:   {goal_type, target_amount, target_date, ...}
    For /plans/chat:   {} — intent_classifier extracts params from user_message
    Written by: FastAPI route (pre-graph).
    Read by: first node in each agent subgraph.
    """

    # ── ROUTING ──────────────────────────────────────────────────────────────
    # Written once by intent_classifier. Read by all conditional edges.

    plan_type: Optional[PlanType]
    """
    Classification result from intent_classifier.
    None until intent_classifier runs (should never be None after routing).
    Written by: intent_classifier.
    Read by: all conditional edges in graph.py.
    """

    # ── V2 BRIDGE DATA ───────────────────────────────────────────────────────
    # Loaded by the first node in each agent subgraph. Read-only after that.

    v2_analytics: Optional[dict]
    """
    Output from V2's deterministic analytics engine (app/analytics/trends.py).
    Contains: rolling averages, category breakdowns, trend classifications.
    This is the real spending history that grounds every projection.
    None if V2 analytics are unavailable → plan cannot be created (DEPENDENCY_UNAVAILABLE).
    Written by: budget_load_v2 / goal_define (first node of each subgraph).
    Read by: budget_optimize, goal_simulate, all checkpoint nodes.
    """

    v2_expenses: Optional[list[dict]]
    """
    Raw expense records for the user from the V2 ledger (app/models/expense.py).
    Used to compute source_hash and to populate audit_payload.expense_snapshot.
    Written by: budget_load_v2 (loads alongside v2_analytics).
    Read by: plan_persist (for source_hash + audit trail).
    """

    # ── DETERMINISTIC OUTPUTS ────────────────────────────────────────────────
    # Written ONLY by simulation nodes. Never written by LLM nodes.
    # Checkpoint nodes re-run the simulation and assert these match.

    projected_outcomes: Optional[dict]
    """
    The numeric outputs of the simulation engine. This is the ground truth.
    Structure varies by plan_type:
      budget:  {monthly_savings, annual_savings, savings_rate, budget_allocation}
      invest:  {equity_pct, debt_pct, liquid_pct, allocation_rationale}
      goal:    {feasibility_label, months_to_goal, gap_amount, contribution_required}
      simulate:{final_balance, total_growth, scenario_comparison}
    Written by: budget_optimize / invest_allocate / goal_simulate / sim_run.
    Read by: checkpoint nodes (to verify), explain nodes (to narrate), plan_persist.
    RULE: LLM explain nodes must NOT write to this field.
    """

    assumptions: Optional[dict]
    """
    The input assumptions used by the simulation engine.
    Stored with the plan so outputs can be reproduced exactly.
    Structure: {income_monthly, inflation_rate, risk_free_rate, growth_rate, ...}
    Written by: budget_optimize / invest_allocate / goal_simulate / sim_run.
    Read by: checkpoint nodes, plan_persist.
    """

    constraints: Optional[dict]
    """
    The constraints applied during optimisation (used by budget_optimize and
    solve_constraints). Stored for auditability.
    Structure: {min_savings_rate, fixed_expenses, user_defined_bounds, ...}
    Written by: budget_optimize.
    Read by: budget_validate (to re-run solve_constraints with same constraints).
    """

    # ── EXTERNAL DATA ────────────────────────────────────────────────────────
    # Written by invest_fetch_data only. Read-only after that.

    external_data: Optional[dict]
    """
    Market data fetched from external APIs (Alpha Vantage / FRED).
    Contains risk-free rate, inflation data, macro indicators.
    GUARDRAIL: invest_explain never receives raw price data from this field.
    It receives only the derived allocation percentages (in projected_outcomes).
    Written by: invest_fetch_data.
    Read by: invest_allocate (to inform allocation), plan_persist (for audit).
    """

    external_freshness: Optional[ExternalFreshness]
    """
    Quality signal for external_data. Propagates to the plan's confidence block.
    "live"     → API call succeeded in this request
    "cached"   → served from TTL cache
    "fallback" → hardcoded fallback rates used (sets degraded=True)
    Written by: invest_fetch_data.
    Read by: plan_persist (confidence block), all agents that set degraded.
    """

    # ── VALIDATION ───────────────────────────────────────────────────────────
    # Written by checkpoint nodes only.

    validation_status: Optional[ValidationStatus]
    """
    Result of the most recently run checkpoint node.
    PASSED → conditional edge routes to LLM explain node.
    FAILED → conditional edge routes to fallback node, LLM is SKIPPED.
    None until first checkpoint runs.
    Written by: budget_validate / invest_validate / goal_validate / sim_validate.
    Read by: conditional edges after each checkpoint.
    """

    validation_errors: Optional[list[str]]
    """
    Human-readable description of what the checkpoint found wrong.
    e.g. ["monthly_savings: got 45000.00, expected 42500.00"]
    Empty list (or None) when validation_status is PASSED.
    Written by: checkpoint nodes on FAILED.
    Read by: fallback nodes (to construct fallback summary), plan_persist (audit).
    """

    # ── LLM OUTPUT ───────────────────────────────────────────────────────────
    # LLM nodes write here. Filter nodes clean here. DB gets only filtered.

    llm_explanation: Optional[str]
    """
    Raw output from the LLM explain node (budget_explain / invest_explain /
    goal_explain). May contain speculative language or hallucinated numbers
    before filtering. NEVER stored to DB or returned to user directly.
    Written by: budget_explain / invest_explain / goal_explain.
    Read by: budget_filter / invest_filter / goal_filter.
    """

    explanation_filtered: Optional[str]
    """
    Cleaned explanation after llm_output_filter.py runs.
    Speculative language removed. Any number not in projected_outcomes removed.
    This is what gets stored in the plan and shown to the user.
    Written by: budget_filter / invest_filter / goal_filter.
    Read by: plan_persist.
    """

    # ── EXECUTION TRACE ──────────────────────────────────────────────────────
    # Appended to by every node. Enables GraphExecutionTrace.tsx.

    graph_trace: list[str]
    """
    Ordered list of node names that have executed for this invocation.
    Every node appends its own name as its first action:
        return {**state, "graph_trace": state["graph_trace"] + ["budget_optimize"]}
    Starts as ["intent_classifier"] after routing.
    Written by: every node (append-only).
    Read by: plan_persist (stored in plan), GET /plans/{id}/trace endpoint.
    NOTE: Not in spec's TypedDict but required by plan output schema and
    needed for GraphExecutionTrace.tsx transparency feature.
    """

    source_hash: Optional[str]
    """
    sha256 of (sorted expense_ids + request_params + PIPELINE_VERSION).
    Computed by plan_persist before the DB write.
    If this hash already exists in the plans table → return existing plan,
    skip recompute (idempotent re-run behaviour from V2 orchestrator).
    Written by: plan_persist.
    Read by: plan_persist (DB lookup), GET /plans/{id} response.
    NOTE: Not in spec's TypedDict but required by plan output schema.
    """

    # ── FINAL OUTPUT ─────────────────────────────────────────────────────────
    # Written by plan_persist. These fields form the stored plan record.

    plan_id: Optional[str]
    """
    UUID of the created plan record. Set after successful DB write.
    None until plan_persist runs.
    Written by: plan_persist.
    Read by: FastAPI route (included in HTTP response to client).
    """

    confidence: Optional[dict]
    """
    Confidence block for this plan. Computed by plan_persist from signals
    collected across the graph run.
    Structure:
        {
            "overall":            float,   # 0.0–1.0
            "data_coverage":      float,   # how complete the V2 data is
            "assumption_risk":    str,     # "low" | "medium" | "high"
            "external_freshness": str,     # mirrors external_freshness field
        }
    Written by: plan_persist.
    Read by: FastAPI route (HTTP response), frontend PlanConfidence.tsx.
    """

    degraded: bool
    """
    True if any of the following occurred:
      - A checkpoint routed to fallback (validation_status == FAILED)
      - External data was unavailable (external_freshness == FALLBACK)
      - LLM explain node timed out (explanation_filtered is the deterministic summary)
      - V2 analytics were partially unavailable
    Shown prominently in the UI so users know the plan ran in reduced mode.
    Written by: checkpoint nodes (on failure), invest_fetch_data (on fallback),
                plan_persist (final consolidation).
    Read by: FastAPI route, frontend StatusBadge.tsx.
    """

    audit_payload: Optional[dict]
    """
    Complete record of all inputs and intermediate state used to produce
    this plan. Stored with the plan for full reproducibility.
    Structure:
        {
            "expense_snapshot":  list[dict],  # v2_expenses at time of run
            "v2_snapshot":       dict,        # v2_analytics at time of run
            "api_snapshot":      dict | None, # external_data at time of run
            "node_timings":      dict,        # {node_name: elapsed_ms}
            "source_hash":       str,
            "pipeline_version":  str,
        }
    Written by: plan_persist.
    Read by: GET /plans/{id} (full audit trail endpoint).
    """


# ---------------------------------------------------------------------------
# Initial state factory
# ---------------------------------------------------------------------------

def make_initial_state(
    user_id: str,
    user_message: str,
    request_params: dict,
) -> VaultAIState:
    """
    Build a fully-initialised VaultAIState ready for graph.invoke().

    Every Optional field is set to None. degraded starts False.
    graph_trace starts as an empty list — intent_classifier appends
    its own name as the first entry.

    Using this factory (rather than hand-building dicts in routes) ensures
    no field is accidentally omitted, which would cause a KeyError the
    first time any node tries to read it.

    Args:
        user_id:        Authenticated user ID from JWT.
        user_message:   Raw natural language input.
        request_params: Structured params from the request body.

    Returns:
        A complete VaultAIState with all fields initialised.
    """
    if not user_id or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")
    if user_message is None:
        raise ValueError("user_message must not be None")
    if request_params is None:
        raise ValueError("request_params must not be None")

    return VaultAIState(
        # Immutable input
        user_id=user_id.strip(),
        user_message=user_message,
        request_params=request_params,
        # Routing
        plan_type=None,
        # V2 bridge
        v2_analytics=None,
        v2_expenses=None,
        # Deterministic outputs
        projected_outcomes=None,
        assumptions=None,
        constraints=None,
        # External data
        external_data=None,
        external_freshness=None,
        # Validation
        validation_status=None,
        validation_errors=None,
        # LLM output
        llm_explanation=None,
        explanation_filtered=None,
        # Execution trace
        graph_trace=[],
        source_hash=None,
        # Final output
        plan_id=None,
        confidence=None,
        degraded=False,
        audit_payload=None,
    )


# ---------------------------------------------------------------------------
# State accessor helpers
# ---------------------------------------------------------------------------
# These are used by nodes and checkpoint functions to read state safely.
# Prefer these over direct dict access so KeyErrors surface with clear messages.

def get_projected_outcomes(state: VaultAIState) -> dict:
    """
    Return projected_outcomes. Raises RuntimeError if None.

    Checkpoint nodes call this to get the value they are about to verify.
    If it's None, something has gone wrong in the node execution order —
    a simulation node should have run before any checkpoint.
    """
    outcomes = state.get("projected_outcomes")
    if outcomes is None:
        raise RuntimeError(
            "projected_outcomes is None in state — simulation node did not run "
            "before checkpoint. Check graph edge ordering in graph.py."
        )
    return outcomes


def get_v2_analytics(state: VaultAIState) -> dict:
    """
    Return v2_analytics. Raises RuntimeError if None.

    Simulation nodes call this to get the V2 data they compute from.
    If it's None, the budget_load_v2 / goal_define node did not run.
    """
    analytics = state.get("v2_analytics")
    if analytics is None:
        raise RuntimeError(
            "v2_analytics is None in state — V2 data loader node did not run. "
            "Check graph edge ordering in graph.py."
        )
    return analytics


def append_trace(state: VaultAIState, node_name: str) -> list[str]:
    """
    Return a new graph_trace list with node_name appended.

    Every node calls this as its first action:
        trace = append_trace(state, "budget_optimize")
        ...
        return {**state, "graph_trace": trace, ...}

    Never mutates state directly — returns a new list so LangGraph's
    immutability contract is respected.
    """
    return state.get("graph_trace", []) + [node_name]


def mark_degraded(state: VaultAIState, reason: str) -> dict:
    """
    Return a partial state update that sets degraded=True and logs the reason
    into audit_payload.degradation_reasons.

    Nodes call this instead of directly setting degraded=True so the reason
    is always recorded for the audit trail.

    Returns a partial dict suitable for merging: {**state, **mark_degraded(...)}
    """
    existing_payload = state.get("audit_payload") or {}
    reasons = existing_payload.get("degradation_reasons", [])
    updated_payload = {
        **existing_payload,
        "degradation_reasons": reasons + [reason],
    }
    return {
        "degraded": True,
        "audit_payload": updated_payload,
    }