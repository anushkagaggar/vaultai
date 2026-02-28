"""
VaultAI V3 — agents/budget/nodes.py
=====================================
Budget agent subgraph: node implementations.

Node execution order in the budget path (matches graph.py topology exactly):

    [budget_load_v2]       ← THIS FILE: fully implemented
         │
    [budget_optimize]      ← THIS FILE: stub (Phase 3 continuation)
         │
    [budget_validate]      ← THIS FILE: stub, passes PASSED by default
         │
    ┌── PASSED ──┐
    │            │
[budget_explain] [budget_fallback]   ← stubs
    │            │
[budget_filter]  │                   ← stub
    └────────────┘
         │
    [plan_persist]

HOW TO WIRE INTO graph.py
--------------------------
Replace the inline stub functions in graph.py with imports from this file:

    # In graph.py, swap the inline stubs for:
    from app.agents.budget.nodes import (
        budget_load_v2,
        budget_optimize,
        budget_validate,
        budget_explain,
        budget_filter,
        budget_fallback,
    )

    # builder.add_node() calls stay identical — only the referenced
    # functions change from local stubs to these implementations.

ASYNC BRIDGE PATTERN
--------------------
V2's build_trends_report() is async (requires AsyncSession + await).
V3's LangGraph nodes are synchronous (graph.invoke() is sync in Phase 2).

The recommended bridge: the FastAPI route (which is already async) calls
build_trends_report() BEFORE invoking the graph, then injects the result
into request_params. This is identical to how runner.py's InsightRunner
works (Step 1 of InsightRunner.run()):

    # In the FastAPI route handler:
    metrics = await build_trends_report(db, current_user.id)
    state = make_initial_state(
        user_id=str(current_user.id),
        user_message=body.message,
        request_params={
            "_plan_type":      "budget",
            "_v2_analytics":   metrics,    # ← pre-fetched here
            "income_monthly":  body.income_monthly,
            ...
        },
    )
    result = app_graph.invoke(state)

This node supports three resolution strategies in priority order:
  1. request_params["_v2_analytics"]  — pre-fetched dict (preferred, zero overhead)
  2. request_params["_db"]            — live AsyncSession, node runs the async call
  3. Neither present                  — DependencyUnavailableError (degraded)

Author: VaultAI V3
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agents.State import (
    VaultAIState,
    ValidationStatus,
    append_trace,
    get_v2_analytics,
    mark_degraded,
)
from app.simulation.optimizer import ALLOCATION_TOLERANCE
from app.analytics.trends import build_trends_report
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentinel exception
# ---------------------------------------------------------------------------

class DependencyUnavailableError(RuntimeError):
    """
    Raised by budget_load_v2 when V2 analytics cannot be loaded.

    The FastAPI route should catch this and return a 503, or the graph's
    error boundary can route to budget_fallback.

    Do NOT catch this inside budget_load_v2 — let it propagate so the
    graph routing layer sees it.
    """


# ---------------------------------------------------------------------------
# Internal: sync wrapper around async build_trends_report()
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Internal: structure validation
# ---------------------------------------------------------------------------

def _validate_trends_report(report: dict, source: str = "budget_load_v2") -> None:
    """
    Assert the trends report from build_trends_report() has the minimum
    required keys that downstream nodes depend on.

    V2 build_trends_report() returns:
        {
            "rolling":    {"30_day_avg": float, "60_day_avg": float, "90_day_avg": float},
            "monthly":    {"current_month": float, "previous_month": float,
                           "percent_change": float | None},
            "trend_type": str,
            "categories": [{"category": str, "total": float}, ...]
        }

    Raises:
        ValueError: with a descriptive message if validation fails.
    """
    REQUIRED_TOP    = {"rolling", "monthly", "trend_type", "categories"}
    REQUIRED_ROLL   = {"30_day_avg", "60_day_avg", "90_day_avg"}
    REQUIRED_MONTH  = {"current_month", "previous_month"}

    missing_top = REQUIRED_TOP - set(report.keys())
    if missing_top:
        raise ValueError(
            f"[{source}] build_trends_report response missing keys: {missing_top}. "
            "V2 schema may have changed."
        )

    missing_roll = REQUIRED_ROLL - set(report.get("rolling", {}).keys())
    if missing_roll:
        raise ValueError(
            f"[{source}] rolling_averages missing keys: {missing_roll}."
        )

    missing_month = REQUIRED_MONTH - set(report.get("monthly", {}).keys())
    if missing_month:
        raise ValueError(
            f"[{source}] monthly_comparison missing keys: {missing_month}."
        )

    if not isinstance(report.get("categories"), list):
        raise ValueError(
            f"[{source}] 'categories' must be a list, "
            f"got {type(report.get('categories')).__name__}."
        )


# ---------------------------------------------------------------------------
# Internal: load metrics for audit_payload
# ---------------------------------------------------------------------------

def _compute_load_metrics(report: dict) -> dict:
    """
    Extract lightweight signals from the trends report.

    Stored in audit_payload["v2_load_metrics"] so plan_persist can build
    the confidence score without re-reading the full analytics object.

    Returns:
        {
            "data_days_available":    int,          ← deepest rolling window with data
            "expense_category_count": int,
            "income_detected":        bool,         ← always False (V2 has no income model)
            "current_month_total":    float,
            "previous_month_total":   float,
            "month_over_month_pct":   float | None,
            "trend_type":             str,
            "top_category":           str | None,
        }
    """
    rolling    = report.get("rolling", {})
    monthly    = report.get("monthly", {})
    categories = report.get("categories", [])

    # Deepest rolling window that has non-zero spend data
    days_available = 0
    for days, key in [(90, "90_day_avg"), (60, "60_day_avg"), (30, "30_day_avg")]:
        val = rolling.get(key)
        if val is not None and val > 0:
            days_available = days
            break

    top_category = categories[0]["category"] if categories else None

    return {
        "data_days_available":    days_available,
        "expense_category_count": len(categories),
        "income_detected":        False,   # V2 has no income model yet
        "current_month_total":    monthly.get("current_month", 0.0),
        "previous_month_total":   monthly.get("previous_month", 0.0),
        "month_over_month_pct":   monthly.get("percent_change"),
        "trend_type":             report.get("trend_type", "unknown"),
        "top_category":           top_category,
    }


# ===========================================================================
# NODE 1: budget_load_v2
# ===========================================================================

async def budget_load_v2(state: VaultAIState) -> VaultAIState:
    """
    LangGraph node: budget_load_v2

    Entry point for the budget agent subgraph. Loads V2 spending analytics
    for the authenticated user and writes them into state.

    ── Reads ────────────────────────────────────────────────────────────────
    state["user_id"]
    state["request_params"]["_v2_analytics"]  — pre-fetched dict (preferred)
    state["request_params"]["_db"]            — AsyncSession fallback

    ── Writes ───────────────────────────────────────────────────────────────
    state["v2_analytics"]   — full dict from build_trends_report()
    state["v2_expenses"]    — [] (plan_persist fetches raw records separately)
    state["graph_trace"]    — "budget_load_v2" appended
    state["audit_payload"]  — "v2_load_metrics" added

    ── V2 output shape (trends.py) ─────────────────────────────────────────
    {
        "rolling":    {"30_day_avg": float, "60_day_avg": float, "90_day_avg": float},
        "monthly":    {"current_month": float, "previous_month": float,
                       "percent_change": float | None},
        "trend_type": "stable" | "moderate_increase" | "spike" | "drop" |
                      "volatile" | "insufficient_data",
        "categories": [{"category": str, "total": float}, ...]  ← up to 5, desc
    }

    ── Degradation ──────────────────────────────────────────────────────────
    On any failure: mark_degraded() is called, DependencyUnavailableError
    is raised. v2_analytics stays None. Graph routes to budget_fallback.

    Raises:
        DependencyUnavailableError
    """
    trace        = append_trace(state, "budget_load_v2")
    user_id      = state["user_id"]
    req_params   = state.get("request_params", {})

    logger.info("budget_load_v2: loading V2 analytics for user_id=%s", user_id)

    analytics_result: dict | None = None
    load_error: str | None        = None

    # ── Strategy 1: pre-fetched dict ──────────────────────────────────────
    if "_v2_analytics" in req_params:
        analytics_result = req_params["_v2_analytics"]
        logger.debug("budget_load_v2: using pre-fetched _v2_analytics")

    # ── Strategy 2: live DB session ───────────────────────────────────────
    elif "_db" in req_params:
        try:
            analytics_result = await build_trends_report(
                req_params["_db"], int(user_id)
            )
        except Exception as exc:
            load_error = f"build_trends_report() raised {type(exc).__name__}: {exc}."

    # ── Strategy 3: nothing provided ─────────────────────────────────────
    else:
        load_error = (
            "budget_load_v2 requires request_params['_v2_analytics'] "
            "or request_params['_db']. Neither found."
        )
        logger.error("budget_load_v2: %s", load_error)

    # ── Guard: None without explicit error ────────────────────────────────
    if load_error is None and analytics_result is None:
        load_error = (
            f"build_trends_report() returned None for user_id={user_id}. "
            "No spending history found."
        )

    # ── Structural validation ─────────────────────────────────────────────
    if load_error is None:
        try:
            _validate_trends_report(analytics_result)
        except ValueError as exc:
            load_error = str(exc)
            logger.error("budget_load_v2: schema validation failed — %s", load_error)

    # ── Fail path: mark degraded + raise ─────────────────────────────────
    if load_error is not None:
        # mark_degraded returns a partial state update dict — we don't return
        # it here because we're about to raise. The calling route/error handler
        # should apply it to state if it catches DependencyUnavailableError.
        mark_degraded(state, load_error)
        raise DependencyUnavailableError(load_error)

    # ── Compute audit metrics ─────────────────────────────────────────────
    load_metrics = _compute_load_metrics(analytics_result)

    logger.info(
        "budget_load_v2: OK — %d categories, %d-day rolling history, trend=%s",
        load_metrics["expense_category_count"],
        load_metrics["data_days_available"],
        load_metrics["trend_type"],
    )

    # ── Merge into audit_payload ──────────────────────────────────────────
    existing_payload: dict = state.get("audit_payload") or {}
    updated_payload = {
        **existing_payload,
        "v2_load_metrics": load_metrics,
    }

    # ── Return updated state ──────────────────────────────────────────────
    return {
        **state,
        "v2_analytics":  analytics_result,
        "v2_expenses":   [],        # plan_persist fetches raw records for source_hash
        "graph_trace":   trace,
        "audit_payload": updated_payload,
    }


# ===========================================================================
# NODE 2: budget_optimize  — STUB
# ===========================================================================

def budget_optimize(state: VaultAIState) -> VaultAIState:
    """
    LangGraph node: budget_optimize

    STUB — implement in Phase 3 after budget_load_v2 is verified in tests.

    ── Will read ────────────────────────────────────────────────────────────
    v2_analytics["categories"]              → expense list (90-day averages)
    v2_analytics["rolling"]["90_day_avg"]   → baseline monthly spend estimate
    request_params["income_monthly"]        → required (V2 has no income model)
    request_params["savings_target_pct"]    → optional, default 0.20 (20%)
    request_params["fixed_expenses"]        → optional list of fixed-priority items

    ── Will write ───────────────────────────────────────────────────────────
    projected_outcomes:
        {
            "monthly_savings":   float,
            "annual_savings":    float,
            "savings_rate":      float,          ← savings / income * 100
            "budget_allocation": dict,           ← full allocate_budget() output
            "optimizer_used":    str,            ← "allocate_budget" | "solve_constraints"
        }
    assumptions:
        {
            "income_monthly":     float,
            "savings_target_pct": float,
            "savings_target_amt": float,
            "data_window_days":   int,
        }
    constraints: dict  ← allocate_budget() / solve_constraints() inputs verbatim,
                          stored so budget_validate can re-run with identical args.

    ── RULES ────────────────────────────────────────────────────────────────
    RULE: No LLM. No external calls. optimizer.py only.
    RULE: ONLY node that writes projected_outcomes on the budget path.
    """
    trace = append_trace(state, "budget_optimize")
    logger.info("budget_optimize: STUB — not yet implemented")
    # TODO Phase 3 implementation:
    #
    # analytics  = get_v2_analytics(state)
    # req        = state.get("request_params", {})
    # income     = float(req.get("income_monthly") or 0)
    # if not income:
    #     raise ValueError("income_monthly is required in request_params for budget plan")
    #
    # target_pct = float(req.get("savings_target_pct", 0.20))
    # target_amt = round(income * target_pct, 2)
    #
    # expenses = _build_expense_list_from_analytics(analytics, req)
    # result   = allocate_budget(income, expenses, target_amt)
    #
    # monthly_savings = result["actual_savings"]
    # savings_rate    = round(monthly_savings / income * 100, 2) if income else 0.0
    #
    # return {
    #     **state,
    #     "graph_trace": trace,
    #     "projected_outcomes": {
    #         "monthly_savings":   round(monthly_savings, 2),
    #         "annual_savings":    round(monthly_savings * 12, 2),
    #         "savings_rate":      savings_rate,
    #         "budget_allocation": result,
    #         "optimizer_used":    "allocate_budget",
    #     },
    #     "assumptions": {
    #         "income_monthly":     income,
    #         "savings_target_pct": target_pct,
    #         "savings_target_amt": target_amt,
    #         "data_window_days":   state["audit_payload"]["v2_load_metrics"]["data_days_available"],
    #     },
    #     "constraints": {
    #         "income_monthly":          income,
    #         "expenses":                expenses,
    #         "savings_target_monthly":  target_amt,
    #     },
    # }
    return {**state, "graph_trace": trace}


# ===========================================================================
# NODE 3: budget_validate  — STUB (passes PASSED)
# ===========================================================================

def budget_validate(state: VaultAIState) -> VaultAIState:
    """
    LangGraph node: budget_validate  (CHECKPOINT)

    STUB — implement alongside budget_optimize in Phase 3.

    ── Will do ──────────────────────────────────────────────────────────────
    Re-run allocate_budget() or solve_constraints() with the exact inputs
    stored in state["constraints"], compare to state["projected_outcomes"].

    On PASSED:
        validation_status = ValidationStatus.PASSED
        validation_errors = []

    On FAILED (mismatch > ALLOCATION_TOLERANCE):
        validation_status = ValidationStatus.FAILED
        validation_errors = ["monthly_savings: got X, expected Y"]
        mark_degraded() called

    Current stub behaviour: always PASSED so Phase 3 graph runs end-to-end.

    ── Phase 3 exit test ────────────────────────────────────────────────────
    Inject projected_outcomes with a tampered monthly_savings value →
    budget_validate must detect it and return ValidationStatus.FAILED.
    """
    trace = append_trace(state, "budget_validate")
    logger.info("budget_validate: STUB — passing with PASSED status")
    return {
        **state,
        "graph_trace":       trace,
        "validation_status": ValidationStatus.PASSED,
        "validation_errors": [],
    }


# ===========================================================================
# NODE 4: budget_explain  — STUB
# ===========================================================================

def budget_explain(state: VaultAIState) -> VaultAIState:
    """
    LangGraph node: budget_explain

    STUB — implement when Groq LLM integration is added.

    ── Will do ──────────────────────────────────────────────────────────────
    Build a prompt from projected_outcomes + assumptions (READ-ONLY).
    Call Groq LLM. Write raw output to llm_explanation.

    RULE: Must NEVER write to projected_outcomes, assumptions, or constraints.
    RULE: Numbers in the prompt must come only from projected_outcomes.
    RULE: If LLM times out → llm_explanation = None, set degraded = True.
          budget_filter handles None by using a deterministic template.
    """
    trace = append_trace(state, "budget_explain")
    logger.info("budget_explain: STUB — not yet implemented")
    return {
        **state,
        "graph_trace":     trace,
        "llm_explanation": None,
    }


# ===========================================================================
# NODE 5: budget_filter  — STUB
# ===========================================================================

def budget_filter(state: VaultAIState) -> VaultAIState:
    """
    LangGraph node: budget_filter

    STUB — implement alongside budget_explain.

    ── Will do ──────────────────────────────────────────────────────────────
    Run llm_output_filter.filter_explanation() on llm_explanation:
      - Strip speculative language
      - Remove numbers not in projected_outcomes
      - Enforce 500-word limit
      - Write to explanation_filtered

    If llm_explanation is None → produce deterministic template from
    projected_outcomes (same template as budget_fallback uses).
    """
    trace = append_trace(state, "budget_filter")
    logger.info("budget_filter: STUB — passing through unfiltered")
    return {
        **state,
        "graph_trace":          trace,
        "explanation_filtered": state.get("llm_explanation"),
    }


# ===========================================================================
# NODE 6: budget_fallback  — STUB
# ===========================================================================

def budget_fallback(state: VaultAIState) -> VaultAIState:
    """
    LangGraph node: budget_fallback

    STUB — implement alongside budget_validate.

    ── When reached ─────────────────────────────────────────────────────────
    budget_validate returns ValidationStatus.FAILED.

    ── Will do ──────────────────────────────────────────────────────────────
    Build a deterministic template summary from projected_outcomes (if
    available) or a "data unavailable" message (if projected_outcomes is None).
    Mark the plan degraded. Write to explanation_filtered.

    RULE: No LLM. Template strings only.
    RULE: explanation_filtered structure must be identical to what budget_filter
          produces — plan_persist cannot distinguish which path was taken.
    """
    trace = append_trace(state, "budget_fallback")
    logger.warning("budget_fallback: STUB — marking degraded, no summary yet")
    degraded_update = mark_degraded(
        state,
        reason=(
            state.get("validation_errors", ["budget_validate FAILED"])[0]
            if state.get("validation_errors")
            else "budget_validate FAILED — using deterministic fallback"
        ),
    )
    return {
        **state,
        **degraded_update,
        "graph_trace":          trace,
        "explanation_filtered": None,  # TODO Phase 3: replace with deterministic template
    }