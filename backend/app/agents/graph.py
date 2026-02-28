"""
VaultAI V3 — agents/graph.py
==============================
The complete LangGraph StateGraph definition.

This file has one job at Phase 2: define the full graph structure so that
graph.compile() succeeds at application startup. Every node exists as a
stub that returns state unchanged. Real logic is added in subsequent phases
— but the topology (nodes, edges, conditional routing) is final here.

WHY TOPOLOGY IS FINAL NOW
--------------------------
LangGraph validates the graph at compile time:
  - Every node referenced in add_edge / add_conditional_edges must exist
  - Every string returned by a routing function must map to a known node
  - The graph must have a reachable END from every path

If we stub nodes but wire edges correctly, the compile test acts as a
continuous integration check: any future node that's accidentally
disconnected or mis-named will fail graph.compile() immediately, not at
runtime when a user hits the endpoint.

GRAPH TOPOLOGY (matches spec Section 2.1 exactly)
--------------------------------------------------

    START
      │
      ▼
  [intent_classifier]          ← rule-based router (Phase 2)
      │
      ├── "budget"   ──►  [budget_load_v2]
      │                        │
      │                   [budget_optimize]    ← simulation engine (Phase 2)
      │                        │
      │                   [budget_validate]    ← CHECKPOINT (Phase 2)
      │                        │
      │              ┌─── PASSED ───┐
      │              │              │
      │         [budget_explain]  [budget_fallback]
      │              │              │
      │         [budget_filter]     │
      │              └──────────────┘
      │                        │
      │                   [plan_persist] ──► END
      │
      ├── "invest"  ──►  [invest_fetch_data]
      │                        │
      │                   [invest_allocate]    ← deterministic templates (Phase 3)
      │                        │
      │                   [invest_validate]    ← CHECKPOINT (Phase 3)
      │                        │
      │              ┌─── PASSED ───┐
      │              │              │
      │         [invest_explain]  [invest_fallback]
      │              │              │
      │         [invest_filter]     │
      │              └──────────────┘
      │                        │
      │                   [plan_persist] ──► END
      │
      ├── "goal"    ──►  [goal_define]
      │                        │
      │                   [goal_simulate]      ← simulation engine (Phase 4)
      │                        │
      │                   [goal_validate]      ← CHECKPOINT (Phase 4)
      │                        │
      │              ┌─── PASSED ───┐
      │              │              │
      │          [goal_explain]  [goal_fallback]
      │              │              │
      │          [goal_filter]      │
      │              └──────────────┘
      │                        │
      │                   [plan_persist] ──► END
      │
      ├── "simulate" ──► [sim_run]             ← no LLM (Phase 4)
      │                        │
      │                   [sim_validate]       ← CHECKPOINT
      │                        │
      │              ┌─── PASSED ───┐
      │              │              │
      │        (no explain)   [sim_fallback]
      │              └──────────────┘
      │                        │
      │                   [plan_persist] ──► END
      │
      ├── "combined" ──► (Phase 5 — all 3 subgraphs in sequence)
      │                   [plan_persist] ──► END
      │
      └── "unknown"  ──► [clarify] ──► END

NOTE ON plan_persist
--------------------
plan_persist is a shared terminal node. All agent paths converge here.
LangGraph handles this correctly — multiple edges pointing to the same
node is valid and common. plan_persist is the only node that writes
to the database.

STUB CONTRACT
-------------
Every stub node:
  1. Appends its own name to graph_trace (uses append_trace helper)
  2. Returns {**state, "graph_trace": trace}
  3. Contains a TODO comment marking where real logic goes
  4. Does NOT raise, does NOT import simulation/LLM/DB modules

This means the compiled graph can actually be invoked with a test state
and will run to completion cleanly (plan_id will be None since plan_persist
is stubbed, but no exceptions will be raised).

Author: VaultAI V3
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.router_node import intent_classifier_node
from app.agents.State import (
    VaultAIState,
    PlanType,
    ValidationStatus,
    append_trace,
    mark_degraded,
)


# ===========================================================================
# ROUTING FUNCTIONS
# These are called by add_conditional_edges. They read state and return
# a string that maps to the next node name.
# ===========================================================================

def _route_by_intent(state: VaultAIState) -> str:
    """
    Called after intent_classifier. Routes to the correct agent subgraph
    based on state["plan_type"].

    Returns one of: "budget_load_v2", "invest_fetch_data", "goal_define",
                    "sim_run", "plan_persist" (combined), "clarify"
    """
    plan_type = state.get("plan_type")

    if plan_type == PlanType.BUDGET:
        return "budget_load_v2"
    elif plan_type == PlanType.INVEST:
        return "invest_fetch_data"
    elif plan_type == PlanType.GOAL:
        return "goal_define"
    elif plan_type == PlanType.SIMULATE:
        return "sim_run"
    elif plan_type == PlanType.COMBINED:
        # Phase 5: all three subgraphs run in sequence.
        # For now routes to budget as the first leg — Phase 5 will
        # replace this with a proper combined orchestration node.
        return "budget_load_v2"
    else:
        # UNKNOWN or None — route to clarify node
        return "clarify"


def _route_after_budget_validate(state: VaultAIState) -> str:
    """
    Called after budget_validate checkpoint.
    PASSED → proceed to LLM explanation
    FAILED / FALLBACK → skip LLM, use deterministic summary
    """
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "budget_explain"
    return "budget_fallback"


def _route_after_invest_validate(state: VaultAIState) -> str:
    """Called after invest_validate checkpoint."""
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "invest_explain"
    return "invest_fallback"


def _route_after_goal_validate(state: VaultAIState) -> str:
    """Called after goal_validate checkpoint."""
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "goal_explain"
    return "goal_fallback"


def _route_after_sim_validate(state: VaultAIState) -> str:
    """Called after sim_validate checkpoint. Simulate path has no LLM explain."""
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "plan_persist"
    return "sim_fallback"


# ===========================================================================
# STUB NODES
# Every node follows the same stub pattern:
#   trace = append_trace(state, "<node_name>")
#   return {**state, "graph_trace": trace}
#
# Real implementations replace the body between the trace line and return.
# ===========================================================================

# ── Budget subgraph ─────────────────────────────────────────────────────────

async def budget_load_v2(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 2 implementation in agents/budget/nodes.py
    Loads V2 analytics and expense records for this user.
    Sets: v2_analytics, v2_expenses
    """
    trace = append_trace(state, "budget_load_v2")
    # TODO: call V2 analytics service, set v2_analytics + v2_expenses
    return {**state, "graph_trace": trace}


def budget_optimize(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 2 implementation in agents/budget/nodes.py
    Calls simulation engine (allocate_budget / solve_constraints).
    Sets: projected_outcomes, assumptions, constraints
    RULE: Only node permitted to write projected_outcomes for budget path.
    """
    trace = append_trace(state, "budget_optimize")
    # TODO: call optimizer.allocate_budget(), set projected_outcomes
    return {**state, "graph_trace": trace}


def budget_validate(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 2 implementation in agents/budget/checkpoint.py
    Re-runs simulation with same inputs. Asserts outputs match projected_outcomes.
    Sets: validation_status, validation_errors
    On mismatch: sets degraded=True via mark_degraded()
    """
    trace = append_trace(state, "budget_validate")
    # TODO: re-run simulation, compare, set validation_status
    return {**state, "graph_trace": trace}


async def budget_explain(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 2 implementation in agents/budget/nodes.py
    Calls Groq LLM. Narrates projected_outcomes only — never derives numbers.
    Sets: llm_explanation
    RULE: Must NOT write to projected_outcomes, assumptions, or constraints.
    """
    trace = append_trace(state, "budget_explain")
    # TODO: call LLM with EXPLANATION_SYSTEM_PROMPT + projected_outcomes
    return {**state, "graph_trace": trace}


def budget_filter(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 2 implementation in agents/filters/llm_output_filter.py
    Scrubs speculative language and hallucinated numbers from llm_explanation.
    Sets: explanation_filtered
    """
    trace = append_trace(state, "budget_filter")
    # TODO: call llm_output_filter.filter_explanation(state["llm_explanation"])
    return {**state, "graph_trace": trace}


def budget_fallback(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 2 implementation in agents/budget/nodes.py
    Runs when budget_validate FAILS. Builds a deterministic summary without LLM.
    Sets: explanation_filtered (from deterministic summary), degraded=True
    """
    trace = append_trace(state, "budget_fallback")
    # TODO: build deterministic summary from projected_outcomes
    return {**state, "graph_trace": trace}


# ── Invest subgraph ─────────────────────────────────────────────────────────

async def invest_fetch_data(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 3 implementation in agents/invest/nodes.py
    Loads V2 analytics AND fetches external market data (Alpha Vantage / FRED).
    Sets: v2_analytics, v2_expenses, external_data, external_freshness
    On API failure: sets external_freshness=FALLBACK, degraded=True
    """
    trace = append_trace(state, "invest_fetch_data")
    # TODO: call V2 service + integrations/market_api.py
    return {**state, "graph_trace": trace}


def invest_allocate(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 3 implementation in agents/invest/nodes.py
    Applies deterministic risk-tolerance → allocation template.
    Sets: projected_outcomes (equity_pct, debt_pct, liquid_pct), assumptions
    GUARDRAIL: Never passes market price data to LLM. LLM receives only
    allocation percentages and risk-free rate.
    """
    trace = append_trace(state, "invest_allocate")
    # TODO: apply allocation template from risk_profile in request_params
    return {**state, "graph_trace": trace}


def invest_validate(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 3 implementation in agents/invest/checkpoint.py
    Key assertion: allocation percentages sum to exactly 100%.
    Also asserts allocation matches the deterministic template for the profile.
    Sets: validation_status, validation_errors
    """
    trace = append_trace(state, "invest_validate")
    # TODO: assert sum(equity+debt+liquid) == 100
    return {**state, "graph_trace": trace}


async def invest_explain(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 3 implementation in agents/invest/nodes.py
    LLM narrates allocation rationale. Receives percentages + risk-free rate only.
    NEVER receives historical return data or market prices.
    Sets: llm_explanation
    """
    trace = append_trace(state, "invest_explain")
    # TODO: call LLM with allocation percentages only
    return {**state, "graph_trace": trace}


def invest_filter(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 3 implementation in agents/filters/llm_output_filter.py
    Scrubs any mention of predicted returns from llm_explanation.
    Sets: explanation_filtered
    """
    trace = append_trace(state, "invest_filter")
    # TODO: call llm_output_filter with invest-specific forbidden patterns
    return {**state, "graph_trace": trace}


def invest_fallback(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 3 implementation in agents/invest/nodes.py
    Deterministic allocation summary without LLM explanation.
    Sets: explanation_filtered, degraded=True
    """
    trace = append_trace(state, "invest_fallback")
    # TODO: build allocation summary from projected_outcomes
    return {**state, "graph_trace": trace}


# ── Goal subgraph ────────────────────────────────────────────────────────────

def goal_define(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation in agents/goal/nodes.py
    Parses goal type and params from request_params. Loads V2 data.
    Sets: v2_analytics, v2_expenses, assumptions (goal inputs)
    Validates: timeline not in the past (raises immediately if so)
    """
    trace = append_trace(state, "goal_define")
    # TODO: parse goal_type, target_amount, target_date from request_params
    return {**state, "graph_trace": trace}


def goal_simulate(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation in agents/goal/nodes.py
    Calls simulation/forecast.py: goal_feasibility() + contribution_required().
    Supports 5 goal types + multi-goal tradeoff (2–5 concurrent goals).
    Sets: projected_outcomes (feasibility_label, months_to_goal, gap_amount,
          contribution_required), constraints
    RULE: Only node permitted to write projected_outcomes for goal path.
    """
    trace = append_trace(state, "goal_simulate")
    # TODO: call forecast.goal_feasibility() and forecast.contribution_required()
    return {**state, "graph_trace": trace}


def goal_validate(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation in agents/goal/checkpoint.py
    Re-runs goal_feasibility() with same inputs. Asserts feasibility_label matches.
    Key test: inject wrong label → checkpoint must catch it.
    Sets: validation_status, validation_errors
    """
    trace = append_trace(state, "goal_validate")
    # TODO: re-run goal_feasibility, assert label and key numbers match
    return {**state, "graph_trace": trace}


async def goal_explain(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation in agents/goal/nodes.py
    LLM narrates the goal feasibility result and timeline.
    Sets: llm_explanation
    """
    trace = append_trace(state, "goal_explain")
    # TODO: call LLM with goal projected_outcomes
    return {**state, "graph_trace": trace}


def goal_filter(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation in agents/filters/llm_output_filter.py
    Sets: explanation_filtered
    """
    trace = append_trace(state, "goal_filter")
    # TODO: scrub speculative language
    return {**state, "graph_trace": trace}


def goal_fallback(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation in agents/goal/nodes.py
    Deterministic feasibility summary when checkpoint fails.
    Sets: explanation_filtered, degraded=True
    """
    trace = append_trace(state, "goal_fallback")
    # TODO: build feasibility summary from projected_outcomes
    return {**state, "graph_trace": trace}


# ── Simulate subgraph ────────────────────────────────────────────────────────

def sim_run(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation in agents/goal/nodes.py (sim path)
    Pure what-if: calls scenarios.build_scenario() / compare_scenarios().
    NO LLM. Deterministic outputs only.
    Sets: projected_outcomes, assumptions
    """
    trace = append_trace(state, "sim_run")
    # TODO: call scenarios.build_scenario() from request_params
    return {**state, "graph_trace": trace}


def sim_validate(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation
    Re-runs build_scenario with same inputs. Asserts final_balance matches.
    Sets: validation_status, validation_errors
    """
    trace = append_trace(state, "sim_validate")
    # TODO: re-run build_scenario, assert final_balance within tolerance
    return {**state, "graph_trace": trace}


def sim_fallback(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 4 implementation
    Returns the raw simulation numbers without validation seal.
    Sets: degraded=True
    """
    trace = append_trace(state, "sim_fallback")
    # TODO: mark degraded, pass projected_outcomes through as-is
    return {**state, "graph_trace": trace}


# ── Shared terminal nodes ───────────────────────────────────────────────────

async def plan_persist(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 2 implementation in plans/service.py
    The ONLY node that writes to the database.
    Computes source_hash, checks for duplicate, writes plan record.
    Sets: plan_id, confidence, source_hash, audit_payload
    On DB failure: raises — transaction rolls back, no partial plan stored.
    """
    trace = append_trace(state, "plan_persist")
    # TODO: compute source_hash, write to DB via plans/service.py
    return {**state, "graph_trace": trace}


def clarify(state: VaultAIState) -> VaultAIState:
    """
    STUB — Phase 5 implementation
    Reached when intent_classifier cannot classify the user's message.
    Sets: explanation_filtered with a helpful clarification prompt.
    Does NOT write a plan to DB (no plan_persist call on this path).
    """
    trace = append_trace(state, "clarify")
    # TODO: generate clarification message based on user_message
    return {**state, "graph_trace": trace}


# ===========================================================================
# GRAPH ASSEMBLY
# ===========================================================================

def _build_graph() -> StateGraph:
    """
    Assemble the complete VaultAI StateGraph.

    Called once by compile_graph(). Separated from compile_graph() so
    tests can inspect the builder before compilation if needed.
    """
    builder = StateGraph(VaultAIState)

    # ── Register all nodes ──────────────────────────────────────────────────
    # Every node name used in add_edge / add_conditional_edges must be
    # registered here first. Typos here → compile error, not runtime error.

    # Router
    builder.add_node("intent_classifier", intent_classifier_node)

    # Budget subgraph
    builder.add_node("budget_load_v2",   budget_load_v2)
    builder.add_node("budget_optimize",  budget_optimize)
    builder.add_node("budget_validate",  budget_validate)
    builder.add_node("budget_explain",   budget_explain)
    builder.add_node("budget_filter",    budget_filter)
    builder.add_node("budget_fallback",  budget_fallback)

    # Invest subgraph
    builder.add_node("invest_fetch_data", invest_fetch_data)
    builder.add_node("invest_allocate",   invest_allocate)
    builder.add_node("invest_validate",   invest_validate)
    builder.add_node("invest_explain",    invest_explain)
    builder.add_node("invest_filter",     invest_filter)
    builder.add_node("invest_fallback",   invest_fallback)

    # Goal subgraph
    builder.add_node("goal_define",    goal_define)
    builder.add_node("goal_simulate",  goal_simulate)
    builder.add_node("goal_validate",  goal_validate)
    builder.add_node("goal_explain",   goal_explain)
    builder.add_node("goal_filter",    goal_filter)
    builder.add_node("goal_fallback",  goal_fallback)

    # Simulate subgraph (no LLM)
    builder.add_node("sim_run",       sim_run)
    builder.add_node("sim_validate",  sim_validate)
    builder.add_node("sim_fallback",  sim_fallback)

    # Shared terminal nodes
    builder.add_node("plan_persist", plan_persist)
    builder.add_node("clarify",      clarify)

    # ── Wire edges ──────────────────────────────────────────────────────────

    # Entry: START → intent_classifier
    builder.set_entry_point("intent_classifier")

    # intent_classifier → conditional branch by plan_type
    builder.add_conditional_edges(
        "intent_classifier",
        _route_by_intent,
        {
            "budget_load_v2":    "budget_load_v2",
            "invest_fetch_data": "invest_fetch_data",
            "goal_define":       "goal_define",
            "sim_run":           "sim_run",
            "clarify":           "clarify",
        },
    )

    # Budget linear chain up to checkpoint
    builder.add_edge("budget_load_v2",  "budget_optimize")
    builder.add_edge("budget_optimize", "budget_validate")

    # budget_validate → conditional: PASSED→explain, FAILED→fallback
    builder.add_conditional_edges(
        "budget_validate",
        _route_after_budget_validate,
        {
            "budget_explain":   "budget_explain",
            "budget_fallback":  "budget_fallback",
        },
    )

    # budget_explain → filter → persist
    builder.add_edge("budget_explain",  "budget_filter")
    builder.add_edge("budget_filter",   "plan_persist")

    # budget_fallback → persist (bypasses LLM entirely)
    builder.add_edge("budget_fallback", "plan_persist")

    # Invest linear chain up to checkpoint
    builder.add_edge("invest_fetch_data", "invest_allocate")
    builder.add_edge("invest_allocate",   "invest_validate")

    # invest_validate → conditional
    builder.add_conditional_edges(
        "invest_validate",
        _route_after_invest_validate,
        {
            "invest_explain":  "invest_explain",
            "invest_fallback": "invest_fallback",
        },
    )

    builder.add_edge("invest_explain",  "invest_filter")
    builder.add_edge("invest_filter",   "plan_persist")
    builder.add_edge("invest_fallback", "plan_persist")

    # Goal linear chain up to checkpoint
    builder.add_edge("goal_define",    "goal_simulate")
    builder.add_edge("goal_simulate",  "goal_validate")

    # goal_validate → conditional
    builder.add_conditional_edges(
        "goal_validate",
        _route_after_goal_validate,
        {
            "goal_explain":  "goal_explain",
            "goal_fallback": "goal_fallback",
        },
    )

    builder.add_edge("goal_explain",  "goal_filter")
    builder.add_edge("goal_filter",   "plan_persist")
    builder.add_edge("goal_fallback", "plan_persist")

    # Simulate chain up to checkpoint
    builder.add_edge("sim_run",      "sim_validate")

    # sim_validate → conditional (no LLM on simulate path)
    builder.add_conditional_edges(
        "sim_validate",
        _route_after_sim_validate,
        {
            "plan_persist": "plan_persist",
            "sim_fallback": "sim_fallback",
        },
    )

    builder.add_edge("sim_fallback", "plan_persist")

    # All paths terminate at plan_persist → END
    builder.add_edge("plan_persist", END)

    # clarify → END (no plan written)
    builder.add_edge("clarify", END)

    return builder


def compile_graph():
    """
    Compile the VaultAI StateGraph and return an executable graph.

    Called once at application startup in main.py:
        from app.agents.graph import compile_graph
        app_graph = compile_graph()

    If this raises, the server must not start. That's intentional —
    a misconfigured graph at startup is better than a silent failure
    at request time.

    Returns:
        A compiled LangGraph CompiledGraph. Use await graph.ainvoke(state)
        from async FastAPI route handlers — NOT graph.invoke().
        graph.invoke() is only safe in sync test scripts.

    Raises:
        Any exception from StateGraph.compile() if the graph is
        misconfigured (missing nodes, unreachable END, etc.)
    """
    builder = _build_graph()
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)