"""
VaultAI V3 — agents/budget/nodes.py   [LLMOps instrumented]
=============================================================
LLMOps changes (all other logic UNCHANGED):
  Phase 1  log_node_start / log_node_end in every node
  Phase 2  track_agent_node to MLflow from budget_optimize, budget_validate
  Phase 3  node_duration + plan_counter Prometheus metrics
           llm_latency + token_counter recorded directly in budget_explain
"""

from __future__ import annotations

import logging
from app.config import settings
import re
import time

import httpx

from app.agents.State import (
    VaultAIState,
    ValidationStatus,
    append_trace,
    get_v2_analytics,
    mark_degraded,
)
from app.simulation.optimizer import allocate_budget, ALLOCATION_TOLERANCE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (unchanged)
# ---------------------------------------------------------------------------

GROQ_API_URL        = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL          = "llama-3.1-8b-instant"
GROQ_TIMEOUT_S      = 15
DEFAULT_SAVINGS_PCT = 0.20

_SPECULATIVE_RE = re.compile(
    r"\b(might|may|could|perhaps|possibly|around|approximately|"
    r"up to|somewhere between|you should consider)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers (unchanged)
# ---------------------------------------------------------------------------

def _validate_trends_report(report: dict) -> None:
    for key in ("rolling", "monthly", "trend_type", "categories"):
        if key not in report:
            raise ValueError(f"V2 analytics missing required key: '{key}'")
    for key in ("30_day_avg", "60_day_avg", "90_day_avg"):
        if key not in report["rolling"]:
            raise ValueError(f"V2 analytics['rolling'] missing key: '{key}'")
    for key in ("current_month", "previous_month"):
        if key not in report["monthly"]:
            raise ValueError(f"V2 analytics['monthly'] missing key: '{key}'")
    if not isinstance(report["categories"], list):
        raise ValueError("V2 analytics['categories'] must be a list")


def _compute_load_metrics(report: dict) -> dict:
    rolling    = report["rolling"]
    monthly    = report["monthly"]
    categories = report["categories"]
    days_available = 0
    for days, key in [(90, "90_day_avg"), (60, "60_day_avg"), (30, "30_day_avg")]:
        val = rolling.get(key)
        if val is not None and float(val) > 0:
            days_available = days
            break
    return {
        "data_days_available":    days_available,
        "expense_category_count": len(categories),
        "income_detected":        False,
        "current_month_total":    monthly.get("current_month", 0.0),
        "previous_month_total":   monthly.get("previous_month", 0.0),
        "month_over_month_pct":   monthly.get("percent_change"),
        "trend_type":             report.get("trend_type", "unknown"),
        "top_category":           categories[0]["category"] if categories else None,
    }


def _build_expense_list(analytics: dict, req_params: dict) -> list[dict]:
    fixed_cats = set(req_params.get("fixed_categories", []))
    expenses   = []
    for rank, cat in enumerate(analytics.get("categories", []), start=1):
        monthly_est = round(float(cat["total"]) / 3.0, 2)
        is_fixed    = cat["category"] in fixed_cats
        expenses.append({
            "category":      cat["category"],
            "amount":        monthly_est,
            "priority":      "fixed" if is_fixed else "flexible",
            "priority_rank": rank,
            "min_amount":    monthly_est if is_fixed else 0.0,
        })
    if not expenses:
        rolling       = analytics.get("rolling", {})
        monthly_total = round(
            float(rolling.get("90_day_avg") or rolling.get("30_day_avg") or 0) / 3.0, 2
        )
        expenses = [{"category": "general", "amount": monthly_total,
                     "priority": "flexible", "priority_rank": 1, "min_amount": 0.0}]
    return expenses


def _build_deterministic_summary(outcomes: dict, assumptions: dict) -> str:
    income  = assumptions.get("income_monthly", 0)
    savings = outcomes.get("monthly_savings", 0)
    rate    = outcomes.get("savings_rate", 0)
    annual  = outcomes.get("annual_savings", 0)
    target  = assumptions.get("savings_target_amt", 0)
    alloc   = outcomes.get("budget_allocation", {})
    status  = alloc.get("status", "UNKNOWN")
    gap     = alloc.get("savings_gap", 0)
    if status == "FEASIBLE":
        return (
            f"Your budget plan is on track. "
            f"With a monthly income of Rs.{income:,.0f}, you can save "
            f"Rs.{savings:,.2f}/month ({rate:.1f}% of income), "
            f"reaching Rs.{annual:,.2f} per year. "
            f"This meets your savings target of Rs.{target:,.0f}/month."
        )
    elif status in ("INFEASIBLE", "DEFICIT"):
        return (
            f"Your savings target of Rs.{target:,.0f}/month is not achievable "
            f"with your current spending pattern. "
            f"There is a shortfall of Rs.{gap:,.2f}. "
            f"Review the category allocations to identify areas to reduce."
        )
    else:
        return (
            f"Budget computed. Monthly savings: Rs.{savings:,.2f} "
            f"({rate:.1f}% of income). Annual savings: Rs.{annual:,.2f}."
        )


# ===========================================================================
# NODE 1 — budget_load_v2  (async)
# ===========================================================================

async def budget_load_v2(state: VaultAIState) -> VaultAIState:
    trace      = append_trace(state, "budget_load_v2")
    user_id    = state["user_id"]
    req_params = state.get("request_params", {})

    # ── LLMOps Phase 1 ───────────────────────────────────────────────────
    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("budget_load_v2", "budget", list(state.keys()))
    t0 = time.perf_counter()

    analytics_result: dict | None = None
    load_error: str | None        = None

    if "_v2_analytics" in req_params:
        analytics_result = req_params["_v2_analytics"]
    elif "_db" in req_params:
        try:
            from app.analytics.trends import build_trends_report
            analytics_result = await build_trends_report(req_params["_db"], int(user_id))
        except Exception as exc:
            load_error = f"build_trends_report() raised {type(exc).__name__}: {exc}"
            logger.error("budget_load_v2: %s", load_error)
    else:
        load_error = ("budget_load_v2 requires request_params['_v2_analytics'] "
                      "or request_params['_db']. Neither was found.")

    if load_error is None and analytics_result is None:
        load_error = f"build_trends_report() returned None for user_id={user_id}"
    if load_error is None:
        try:
            _validate_trends_report(analytics_result)
        except ValueError as exc:
            load_error = str(exc)

    if load_error is not None:
        logger.error("budget_load_v2: DEPENDENCY_UNAVAILABLE — %s", load_error)
        raise RuntimeError(f"budget_load_v2 failed: {load_error}")

    load_metrics     = _compute_load_metrics(analytics_result)
    existing_payload = state.get("audit_payload") or {}

    log_node_end("budget_load_v2", "budget",
                 round((time.perf_counter() - t0) * 1000, 1), "success",
                 {"data_days_available": load_metrics["data_days_available"],
                  "category_count": load_metrics["expense_category_count"]})

    logger.info("budget_load_v2: OK — %d categories, %d-day history, trend=%s",
                load_metrics["expense_category_count"],
                load_metrics["data_days_available"],
                load_metrics["trend_type"])

    return {
        **state,
        "v2_analytics":  analytics_result,
        "v2_expenses":   [],
        "graph_trace":   trace,
        "audit_payload": {**existing_payload, "v2_load_metrics": load_metrics},
    }


# ===========================================================================
# NODE 2 — budget_optimize  (sync)
# ===========================================================================

def budget_optimize(state: VaultAIState) -> VaultAIState:
    trace      = append_trace(state, "budget_optimize")
    analytics  = get_v2_analytics(state)
    req_params = state.get("request_params", {})

    # ── LLMOps Phase 1 ───────────────────────────────────────────────────
    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("budget_optimize", "budget", list(state.keys()))
    t0 = time.perf_counter()

    income_raw = req_params.get("income_monthly")
    if not income_raw:
        raise ValueError("income_monthly is required in request_params for a budget plan.")
    income     = float(income_raw)
    target_pct = float(req_params.get("savings_target_pct", DEFAULT_SAVINGS_PCT))
    target_amt = round(income * target_pct, 2)
    expenses   = _build_expense_list(analytics, req_params)

    result          = allocate_budget(income, expenses, target_amt, allow_deficit=False)
    monthly_savings = result["actual_savings"]
    savings_rate    = round(monthly_savings / income * 100, 2) if income else 0.0
    opt_status      = result["status"]

    duration_ms  = round((time.perf_counter() - t0) * 1000, 1)
    node_metrics = {
        "savings_rate":    savings_rate,
        "monthly_savings": round(monthly_savings, 2),
        "annual_savings":  round(monthly_savings * 12, 2),
        "convergence_ok":  opt_status == "FEASIBLE",
        "optimizer_used":  "allocate_budget",
    }

    # Phase 1
    log_node_end("budget_optimize", "budget", duration_ms,
                 "success" if opt_status == "FEASIBLE" else "fallback", node_metrics)

    # Phase 2
    try:
        from app.agents.mlflow_tracker import track_agent_node
        track_agent_node("budget_optimize", "budget", duration_ms,
                         "success" if opt_status == "FEASIBLE" else "fallback", node_metrics)
    except Exception:
        pass

    # Phase 3
    try:
        from app.metrics import node_duration, plan_counter
        node_duration.labels("budget_optimize", "budget").observe(duration_ms / 1000)
        plan_counter.labels("budget", "success" if opt_status == "FEASIBLE" else "degraded").inc()
    except Exception:
        pass

    logger.info("budget_optimize: income=%.0f target=%.0f(%.0f%%) savings=%.0f status=%s",
                income, target_amt, target_pct * 100, monthly_savings, opt_status)

    constraints = {
        "income_monthly":         income,
        "expenses":               expenses,
        "savings_target_monthly": target_amt,
        "allow_deficit":          False,
    }
    return {
        **state,
        "graph_trace": trace,
        "projected_outcomes": {
            "monthly_savings":   round(monthly_savings, 2),
            "annual_savings":    round(monthly_savings * 12, 2),
            "savings_rate":      savings_rate,
            "budget_allocation": result,
            "optimizer_used":    "allocate_budget",
        },
        "assumptions": {
            "income_monthly":      income,
            "savings_target_pct":  target_pct,
            "savings_target_amt":  target_amt,
            "data_days_available": (state.get("audit_payload") or {})
                                   .get("v2_load_metrics", {})
                                   .get("data_days_available", 0),
        },
        "constraints": constraints,
    }


# ===========================================================================
# NODE 3 — budget_validate  (sync checkpoint)
# ===========================================================================

def budget_validate(state: VaultAIState) -> VaultAIState:
    trace  = append_trace(state, "budget_validate")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("budget_validate", "budget", list(state.keys()))
    t0 = time.perf_counter()

    stored = state.get("projected_outcomes")
    cons   = state.get("constraints")

    def _fail(reason, errors_list):
        log_node_end("budget_validate", "budget",
                     round((time.perf_counter() - t0) * 1000, 1), "failed",
                     {"validation_passed": False, "errors_found": len(errors_list)})
        degraded_patch = mark_degraded(state, reason)
        return {**state, **degraded_patch,
                "graph_trace": trace,
                "validation_status": ValidationStatus.FAILED,
                "validation_errors": errors_list}

    if stored is None or cons is None:
        reason = "projected_outcomes or constraints missing — budget_optimize did not run"
        logger.error("budget_validate: %s", reason)
        return _fail(reason, [reason])

    try:
        recomputed = allocate_budget(
            income_monthly         = cons["income_monthly"],
            expenses               = cons["expenses"],
            savings_target_monthly = cons["savings_target_monthly"],
            allow_deficit          = cons.get("allow_deficit", False),
        )
    except Exception as exc:
        reason = f"allocate_budget() re-run raised {type(exc).__name__}: {exc}"
        logger.error("budget_validate: %s", reason)
        return _fail(reason, [reason])

    errors: list[str] = []
    stored_savings     = stored.get("monthly_savings", 0.0)
    recomputed_savings = round(recomputed["actual_savings"], 2)
    if abs(stored_savings - recomputed_savings) > ALLOCATION_TOLERANCE:
        errors.append(f"monthly_savings mismatch: stored={stored_savings}, "
                      f"recomputed={recomputed_savings}")
    stored_status     = stored.get("budget_allocation", {}).get("status")
    recomputed_status = recomputed["status"]
    if stored_status != recomputed_status:
        errors.append(f"allocation status mismatch: stored={stored_status}, "
                      f"recomputed={recomputed_status}")

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    if errors:
        logger.warning("budget_validate: FAILED — %s", errors)
        log_node_end("budget_validate", "budget", duration_ms, "failed",
                     {"validation_passed": False, "errors_found": len(errors)})
        try:
            from app.agents.mlflow_tracker import track_agent_node
            track_agent_node("budget_validate", "budget", duration_ms, "failed",
                             {"validation_passed": 0.0})
        except Exception:
            pass
        degraded_patch = mark_degraded(state, "; ".join(errors))
        return {**state, **degraded_patch,
                "graph_trace": trace,
                "validation_status": ValidationStatus.FAILED,
                "validation_errors": errors}

    logger.info("budget_validate: PASSED")
    log_node_end("budget_validate", "budget", duration_ms, "success",
                 {"validation_passed": True})
    try:
        from app.agents.mlflow_tracker import track_agent_node
        track_agent_node("budget_validate", "budget", duration_ms, "success",
                         {"validation_passed": 1.0})
    except Exception:
        pass
    return {**state,
            "graph_trace":       trace,
            "validation_status": ValidationStatus.PASSED,
            "validation_errors": []}


# ===========================================================================
# NODE 4 — budget_explain  (async Groq)
# ===========================================================================

async def budget_explain(state: VaultAIState) -> VaultAIState:
    trace       = append_trace(state, "budget_explain")
    outcomes    = state.get("projected_outcomes") or {}
    assumptions = state.get("assumptions") or {}
    analytics   = state.get("v2_analytics") or {}

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("budget_explain", "budget", list(state.keys()))
    t0 = time.perf_counter()

    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("budget_explain: GROQ_API_KEY not set — skipping LLM")
        log_node_end("budget_explain", "budget",
                     round((time.perf_counter() - t0) * 1000, 1), "fallback",
                     {"llm_skipped": True})
        degraded_patch = mark_degraded(state, "GROQ_API_KEY not configured")
        return {**state, **degraded_patch, "graph_trace": trace, "llm_explanation": None}

    allocation  = outcomes.get("budget_allocation", {})
    alloc_lines = "\n".join(
        f"  {a['category']}: Rs.{a['allocated']:,.0f}"
        + (f" (cut Rs.{a['cut_amount']:,.0f})" if a.get("cut_amount", 0) > 0 else "")
        for a in allocation.get("allocations", [])
    ) or "  No breakdown available."

    system_prompt = (
        "You are a financial planning assistant. Explain this budget plan in plain "
        "English. STRICT RULES: (1) Use ONLY the numbers shown in the user message. "
        "(2) Do not speculate, estimate, or add numbers not listed. "
        "(3) Write exactly 3-5 sentences. (4) Address the user directly."
    )
    user_content = (
        f"Budget plan:\n"
        f"Monthly income: Rs.{assumptions.get('income_monthly', 0):,.0f}\n"
        f"Monthly savings: Rs.{outcomes.get('monthly_savings', 0):,.2f} "
        f"({outcomes.get('savings_rate', 0):.1f}% of income)\n"
        f"Annual savings: Rs.{outcomes.get('annual_savings', 0):,.2f}\n"
        f"Budget status: {allocation.get('status', 'unknown')}\n"
        f"Savings target: Rs.{assumptions.get('savings_target_amt', 0):,.0f}/month\n"
        f"Spending trend: {analytics.get('trend_type', 'unknown')}\n"
        f"Category allocations:\n{alloc_lines}"
    )

    msg = ""
    try:
        async with httpx.AsyncClient(timeout=GROQ_TIMEOUT_S) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL,
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user",   "content": user_content}],
                      "temperature": 0.2, "max_tokens": 300},
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()

            # ── LLMOps Phase 1+2+3 ───────────────────────────────────────
            latency_ms        = round((time.perf_counter() - t0) * 1000, 1)
            usage             = resp.json().get("usage", {})
            prompt_tokens     = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            from app.agents.ops_logger import log_llm_call
            log_llm_call("budget", GROQ_MODEL, prompt_tokens, completion_tokens, latency_ms)
            log_node_end("budget_explain", "budget", latency_ms, "success",
                         {"explanation_length_chars": len(raw),
                          "prompt_tokens": prompt_tokens,
                          "completion_tokens": completion_tokens})

            try:
                from app.agents.mlflow_tracker import track_llm_call, track_agent_node
                track_llm_call("budget", GROQ_MODEL, prompt_tokens, completion_tokens,
                               latency_ms, user_content[:500], raw)
                track_agent_node("budget_explain", "budget", latency_ms, "success",
                                 {"prompt_tokens": float(prompt_tokens),
                                  "completion_tokens": float(completion_tokens),
                                  "explanation_length_chars": float(len(raw))})
            except Exception:
                pass

            try:
                from app.metrics import llm_latency, token_counter, node_duration
                llm_latency.labels("budget").observe(latency_ms / 1000)
                token_counter.labels("prompt").inc(prompt_tokens)
                token_counter.labels("completion").inc(completion_tokens)
                node_duration.labels("budget_explain", "budget").observe(latency_ms / 1000)
            except Exception:
                pass

        logger.info("budget_explain: LLM OK (%d chars)", len(raw))
        return {**state, "graph_trace": trace, "llm_explanation": raw}

    except httpx.TimeoutException:
        msg = f"Groq timed out after {GROQ_TIMEOUT_S}s"
        logger.warning("budget_explain: %s", msg)
    except httpx.HTTPStatusError as exc:
        try:    error_body = exc.response.text
        except Exception: error_body = "(could not read response body)"
        msg = f"Groq HTTP {exc.response.status_code}: {error_body}"
        logger.error("budget_explain: %s", msg)
    except Exception as exc:
        msg = f"Groq call failed: {type(exc).__name__}: {exc}"
        logger.error("budget_explain: %s", msg)

    log_node_end("budget_explain", "budget",
                 round((time.perf_counter() - t0) * 1000, 1), "fallback",
                 {"llm_failed": True})
    degraded_patch = mark_degraded(state, msg)
    return {**state, **degraded_patch, "graph_trace": trace, "llm_explanation": None}


# ===========================================================================
# NODE 5 — budget_filter  (sync)
# ===========================================================================

def budget_filter(state: VaultAIState) -> VaultAIState:
    trace    = append_trace(state, "budget_filter")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("budget_filter", "budget", list(state.keys()))
    t0 = time.perf_counter()

    raw      = state.get("llm_explanation")
    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}

    if raw is None:
        filtered = _build_deterministic_summary(outcomes, assum)
        logger.info("budget_filter: LLM was None — deterministic summary used")
    else:
        from app.agents.filters.llm_output_filter import filter_llm_output
        result   = filter_llm_output(raw, outcomes, assum)
        filtered = result.text_clean
        logger.info("budget_filter: %d→%d chars", len(raw), len(filtered))

    log_node_end("budget_filter", "budget",
                 round((time.perf_counter() - t0) * 1000, 1), "success",
                 {"output_length": len(filtered)})

    return {**state, "graph_trace": trace, "explanation_filtered": filtered}


# ===========================================================================
# NODE 6 — budget_fallback  (sync)
# ===========================================================================

def budget_fallback(state: VaultAIState) -> VaultAIState:
    trace    = append_trace(state, "budget_fallback")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("budget_fallback", "budget", list(state.keys()))
    t0 = time.perf_counter()

    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}
    errors   = state.get("validation_errors") or ["validation failed"]
    reason   = errors[0]

    degraded_patch = mark_degraded(state, reason)
    summary = (
        _build_deterministic_summary(outcomes, assum) if outcomes
        else ("Unable to generate a budget plan: spending data could not be "
              "validated. Please try again or contact support.")
    )

    try:
        from app.metrics import plan_counter, execution_state_counter
        plan_counter.labels("budget", "degraded").inc()
        execution_state_counter.labels("budget", "fallback").inc()
    except Exception:
        pass

    log_node_end("budget_fallback", "budget",
                 round((time.perf_counter() - t0) * 1000, 1), "fallback",
                 {"reason": reason[:200]})

    logger.warning("budget_fallback: degraded — %s", reason)
    return {**state, **degraded_patch,
            "graph_trace": trace, "explanation_filtered": summary}