"""
VaultAI V3 — agents/goal/nodes.py   [LLMOps instrumented]
==========================================================
LLMOps changes only — all business logic unchanged.
"""

from __future__ import annotations

import logging
from app.config import settings
import re
import time
from datetime import date, datetime

import httpx

from app.agents.State import (
    VaultAIState,
    ValidationStatus,
    append_trace,
    get_v2_analytics,
    mark_degraded,
)
from app.simulation.forecast import (
    goal_feasibility,
    contribution_required,
    debt_payoff_schedule,
    multi_goal_tradeoff,
)

logger = logging.getLogger(__name__)

GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL     = "llama-3.1-8b-instant"
GROQ_TIMEOUT_S = 15
DEFAULT_ANNUAL_RATE = 0.07

VALID_GOAL_TYPES = {
    "savings", "emergency_fund", "purchase", "education", "retirement",
    "travel", "debt_payoff", "multi_goal",
}

_SPECULATIVE_RE = re.compile(
    r"\b(might|may|could|perhaps|possibly|around|approximately|"
    r"up to|somewhere between|you should consider|guaranteed)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers (unchanged)
# ---------------------------------------------------------------------------

def _validate_trends_report(report: dict) -> None:
    for key in ("rolling", "monthly", "trend_type", "categories"):
        if key not in report:
            raise ValueError(f"V2 analytics missing required key: '{key}'")


def _derive_monthly_savings(analytics: dict, req_params: dict) -> float:
    if "monthly_savings" in req_params:
        return float(req_params["monthly_savings"])
    income = float(req_params.get("income_monthly", 0))
    rolling = analytics.get("rolling", {})
    monthly_spend = round(
        float(rolling.get("90_day_avg") or rolling.get("30_day_avg") or 0) / 3.0, 2)
    if income > monthly_spend > 0:
        return round(income - monthly_spend, 2)
    return 0.0


def _horizon_from_target_date(target_date_str: str) -> int:
    try:
        target = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"target_date must be YYYY-MM-DD format, got '{target_date_str}'")
    today = date.today()
    if target <= today:
        raise ValueError(f"target_date '{target_date_str}' is in the past (today={today}).")
    months = (target.year - today.year) * 12 + (target.month - today.month)
    if target.day < today.day:
        months -= 1
    return max(1, months)


def _build_deterministic_summary(outcomes: dict, assumptions: dict) -> str:
    label      = outcomes.get("feasibility_label", "UNKNOWN")
    target     = assumptions.get("target_amount", 0)
    horizon    = assumptions.get("horizon_months", 0)
    contrib    = outcomes.get("contribution_required", 0)
    monthly_sv = assumptions.get("monthly_savings", 0)
    gap        = outcomes.get("gap_amount", 0)
    months_to  = outcomes.get("months_to_goal")
    goal_type  = assumptions.get("goal_type", "goal")
    if label == "FEASIBLE":
        if months_to and months_to < horizon:
            return (f"Your {goal_type} goal of Rs.{target:,.0f} is achievable. "
                    f"At Rs.{monthly_sv:,.0f}/month you will reach it in {months_to} months, "
                    f"ahead of your {horizon}-month target.")
        return (f"Your {goal_type} goal of Rs.{target:,.0f} is achievable. "
                f"Saving Rs.{monthly_sv:,.0f}/month for {horizon} months will reach your target.")
    elif label == "STRETCH":
        return (f"Your {goal_type} goal of Rs.{target:,.0f} is a stretch. "
                f"You are Rs.{gap:,.0f} short at your current savings rate. "
                f"Increasing to Rs.{contrib:,.0f}/month would make it achievable in {horizon} months.")
    else:
        return (f"Your {goal_type} goal of Rs.{target:,.0f} is not achievable "
                f"in {horizon} months at your current savings rate. "
                f"You need Rs.{contrib:,.0f}/month to reach this goal. "
                f"Consider extending your timeline or reducing the target amount.")


# ===========================================================================
# NODE 1 — goal_define
# ===========================================================================

async def goal_define(state: VaultAIState) -> VaultAIState:
    trace      = append_trace(state, "goal_define")
    user_id    = state["user_id"]
    req_params = state.get("request_params", {})

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("goal_define", "goal", list(state.keys()))
    t0 = time.perf_counter()

    goal_type = str(req_params.get("goal_type", "")).lower().strip()
    if not goal_type:
        raise ValueError("goal_type is required in request_params.")
    if goal_type not in VALID_GOAL_TYPES:
        raise ValueError(f"Invalid goal_type '{goal_type}'.")

    target_amount = req_params.get("target_amount")
    if not target_amount or float(target_amount) <= 0:
        raise ValueError("target_amount must be a positive number in request_params.")

    target_date_str = req_params.get("target_date")
    if target_date_str:
        horizon_months = _horizon_from_target_date(str(target_date_str))
    else:
        horizon_months = req_params.get("horizon_months")
        if not horizon_months or int(horizon_months) <= 0:
            raise ValueError("horizon_months must be a positive integer in request_params.")
        horizon_months = int(horizon_months)

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
            logger.error("goal_define: %s", load_error)
    else:
        load_error = ("goal_define requires request_params['_v2_analytics'] "
                      "or request_params['_db']. Neither was found.")

    if load_error is None and analytics_result is None:
        load_error = f"build_trends_report() returned None for user_id={user_id}"
    if load_error is None:
        try: _validate_trends_report(analytics_result)
        except ValueError as exc: load_error = str(exc)

    if load_error is not None:
        logger.error("goal_define: DEPENDENCY_UNAVAILABLE — %s", load_error)
        raise RuntimeError(f"goal_define failed: {load_error}")

    existing_payload = state.get("audit_payload") or {}

    log_node_end("goal_define", "goal",
                 round((time.perf_counter() - t0) * 1000, 1), "success",
                 {"goal_type": goal_type, "horizon_months": horizon_months})

    logger.info("goal_define: OK — type=%s target=%.0f horizon=%d months",
                goal_type, float(target_amount), horizon_months)

    return {
        **state,
        "v2_analytics":  analytics_result,
        "v2_expenses":   [],
        "graph_trace":   trace,
        "audit_payload": {
            **existing_payload,
            "v2_load_metrics": {"data_days_available": 90},
            "goal_params": {"goal_type": goal_type,
                            "target_amount": float(target_amount),
                            "horizon_months": horizon_months},
        },
    }


# ===========================================================================
# NODE 2 — goal_simulate
# ===========================================================================

def goal_simulate(state: VaultAIState) -> VaultAIState:
    trace      = append_trace(state, "goal_simulate")
    analytics  = get_v2_analytics(state)
    req_params = state.get("request_params", {})

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("goal_simulate", "goal", list(state.keys()))
    t0 = time.perf_counter()

    goal_type       = str(req_params.get("goal_type", "goal")).lower()
    target_amount   = float(req_params["target_amount"])
    current_savings = float(req_params.get("current_savings", 0))
    annual_rate     = float(req_params.get("annual_rate", DEFAULT_ANNUAL_RATE))
    monthly_savings = _derive_monthly_savings(analytics, req_params)

    target_date_str = req_params.get("target_date")
    if target_date_str:
        horizon_months = _horizon_from_target_date(str(target_date_str))
    else:
        horizon_months = int(req_params.get("horizon_months", 12))

    if goal_type == "debt_payoff":
        outstanding     = float(req_params.get("outstanding", target_amount))
        interest_rate   = float(req_params.get("interest_rate", annual_rate))
        monthly_payment = float(req_params.get("monthly_payment", monthly_savings))
        schedule = debt_payoff_schedule(outstanding=outstanding,
                                        annual_interest_rate=interest_rate,
                                        monthly_payment=monthly_payment)
        projected_outcomes = {
            "goal_type": goal_type, "outstanding": outstanding,
            "monthly_payment": monthly_payment,
            "total_months": schedule["total_months"],
            "total_interest_paid": schedule["total_interest_paid"],
            "total_paid": schedule["total_paid"],
            "interest_saved": schedule["interest_saved"],
            "payment_sufficient": schedule["payment_sufficient"],
            "feasibility_label": "FEASIBLE" if schedule["payment_sufficient"] else "INFEASIBLE",
            "projected_balance": 0.0, "gap_amount": 0.0, "surplus": 0.0,
            "coverage_ratio": 1.0 if schedule["payment_sufficient"] else 0.0,
            "contribution_required": monthly_payment,
            "payoff_schedule": schedule["payoff_schedule"],
        }
        assumptions  = {"goal_type": goal_type, "target_amount": outstanding,
                        "horizon_months": schedule.get("total_months") or horizon_months,
                        "current_savings": 0.0, "monthly_savings": monthly_payment,
                        "annual_rate": interest_rate}
        constraints  = {"goal_type": goal_type, "outstanding": outstanding,
                        "interest_rate": interest_rate, "monthly_payment": monthly_payment}

    elif goal_type == "multi_goal":
        sub_goals = req_params.get("sub_goals", [])
        if not sub_goals or len(sub_goals) < 2:
            raise ValueError("multi_goal requires 'sub_goals' list with 2-5 goal dicts.")
        tradeoff = multi_goal_tradeoff(goals=sub_goals,
                                       total_monthly_available=monthly_savings,
                                       annual_rate=annual_rate)
        feasible_count = sum(1 for a in tradeoff["allocations"]
                             if a["feasibility"]["label"] == "FEASIBLE")
        total_count = len(tradeoff["allocations"])
        overall_label = ("FEASIBLE" if feasible_count == total_count
                         else "STRETCH" if feasible_count >= total_count // 2
                         else "INFEASIBLE")
        projected_outcomes = {
            "goal_type": goal_type, "feasibility_label": overall_label,
            "feasible_goals": feasible_count, "total_goals": total_count,
            "total_monthly_allocated": tradeoff["total_allocated"],
            "unallocated": tradeoff["unallocated"],
            "allocations": tradeoff["allocations"],
            "tradeoff_summary": tradeoff["tradeoff_summary"],
            "projected_balance": 0.0, "gap_amount": 0.0, "surplus": 0.0,
            "coverage_ratio": round(feasible_count / total_count, 4),
            "contribution_required": monthly_savings, "months_to_goal": None,
        }
        assumptions = {"goal_type": goal_type,
                       "target_amount": sum(g.get("target_amount", 0) for g in sub_goals),
                       "horizon_months": horizon_months, "current_savings": 0.0,
                       "monthly_savings": monthly_savings, "annual_rate": annual_rate}
        constraints = {"goal_type": goal_type,
                       "total_monthly_available": monthly_savings,
                       "annual_rate": annual_rate, "sub_goals": sub_goals}

    else:
        feasibility = goal_feasibility(
            target_amount=target_amount, current_savings=current_savings,
            monthly_savings=monthly_savings, annual_rate=annual_rate,
            horizon_months=horizon_months)
        required = contribution_required(
            target_amount=target_amount, current_savings=current_savings,
            annual_rate=annual_rate, horizon_months=horizon_months)
        logger.info("goal_simulate: type=%s target=%.0f horizon=%d "
                    "monthly_savings=%.0f label=%s coverage=%.2f",
                    goal_type, target_amount, horizon_months,
                    monthly_savings, feasibility["label"], feasibility["coverage_ratio"])
        projected_outcomes = {
            "goal_type": goal_type,
            "feasibility_label": feasibility["label"],
            "projected_balance": feasibility["projected_balance"],
            "gap_amount": feasibility["gap_amount"],
            "surplus": feasibility["surplus"],
            "months_to_goal": feasibility["months_to_goal"],
            "coverage_ratio": feasibility["coverage_ratio"],
            "contribution_required": required["monthly_contribution_required"],
            "total_to_contribute": required["total_to_contribute"],
            "is_already_feasible": required["is_already_feasible"],
        }
        assumptions = {"goal_type": goal_type, "target_amount": target_amount,
                       "horizon_months": horizon_months, "current_savings": current_savings,
                       "monthly_savings": monthly_savings, "annual_rate": annual_rate}
        constraints = {"goal_type": goal_type, "target_amount": target_amount,
                       "current_savings": current_savings, "monthly_savings": monthly_savings,
                       "annual_rate": annual_rate, "horizon_months": horizon_months}

    feasibility_label = projected_outcomes.get("feasibility_label", "UNKNOWN")
    coverage_ratio    = projected_outcomes.get("coverage_ratio", 0)
    duration_ms       = round((time.perf_counter() - t0) * 1000, 1)
    node_metrics      = {"goal_type": goal_type,
                         "feasibility_label": feasibility_label,
                         "coverage_ratio": coverage_ratio,
                         "contribution_required": float(projected_outcomes.get("contribution_required", 0)),
                         "horizon_months": float(horizon_months)}

    log_node_end("goal_simulate", "goal", duration_ms, "success", node_metrics)

    try:
        from app.agents.mlflow_tracker import track_agent_node
        track_agent_node("goal_simulate", "goal", duration_ms, "success",
                         {"coverage_ratio": coverage_ratio,
                          "contribution_required": float(projected_outcomes.get("contribution_required", 0)),
                          "horizon_months": float(horizon_months)})
    except Exception: pass

    try:
        from app.metrics import node_duration, plan_counter
        node_duration.labels("goal_simulate", "goal").observe(duration_ms / 1000)
        plan_counter.labels("goal",
                            "success" if feasibility_label in ("FEASIBLE", "STRETCH")
                            else "degraded").inc()
    except Exception: pass

    return {**state,
            "graph_trace":        trace,
            "projected_outcomes": projected_outcomes,
            "assumptions":        assumptions,
            "constraints":        constraints}


# ===========================================================================
# NODE 3 — goal_validate
# ===========================================================================

def goal_validate(state: VaultAIState) -> VaultAIState:
    from app.agents.goal.checkpoint import run_goal_checkpoint
    trace  = append_trace(state, "goal_validate")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("goal_validate", "goal", list(state.keys()))
    t0 = time.perf_counter()

    stored = state.get("projected_outcomes")
    cons   = state.get("constraints")

    if stored is None or cons is None:
        reason = "projected_outcomes or constraints missing — goal_simulate did not run"
        logger.error("goal_validate: %s", reason)
        log_node_end("goal_validate", "goal",
                     round((time.perf_counter() - t0) * 1000, 1), "failed",
                     {"validation_passed": False})
        return {**state, **mark_degraded(state, reason),
                "graph_trace": trace,
                "validation_status": ValidationStatus.FAILED,
                "validation_errors": [reason]}

    result      = run_goal_checkpoint(stored, cons)
    duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    log_node_end("goal_validate", "goal", duration_ms,
                 "success" if result.passed else "failed",
                 {"validation_passed": result.passed})

    try:
        from app.agents.mlflow_tracker import track_agent_node
        track_agent_node("goal_validate", "goal", duration_ms,
                         "success" if result.passed else "failed",
                         {"validation_passed": float(result.passed)})
    except Exception: pass

    if not result.passed:
        logger.warning("goal_validate: FAILED — %s", result.errors)
        return {**state, **mark_degraded(state, result.errors[0]),
                "graph_trace": trace,
                "validation_status": ValidationStatus.FAILED,
                "validation_errors": result.errors}

    logger.info("goal_validate: PASSED — label=%s", stored.get("feasibility_label"))
    return {**state,
            "graph_trace":       trace,
            "validation_status": ValidationStatus.PASSED,
            "validation_errors": []}


# ===========================================================================
# NODE 4 — goal_explain
# ===========================================================================

async def goal_explain(state: VaultAIState) -> VaultAIState:
    trace       = append_trace(state, "goal_explain")
    outcomes    = state.get("projected_outcomes") or {}
    assumptions = state.get("assumptions") or {}

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("goal_explain", "goal", list(state.keys()))
    t0 = time.perf_counter()

    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("goal_explain: GROQ_API_KEY not set — skipping LLM")
        log_node_end("goal_explain", "goal",
                     round((time.perf_counter() - t0) * 1000, 1), "fallback",
                     {"llm_skipped": True})
        return {**state, **mark_degraded(state, "GROQ_API_KEY not configured"),
                "graph_trace": trace, "llm_explanation": None}

    label     = outcomes.get("feasibility_label", "UNKNOWN")
    target    = assumptions.get("target_amount", 0)
    horizon   = assumptions.get("horizon_months", 0)
    goal_type = assumptions.get("goal_type", "goal")
    monthly   = assumptions.get("monthly_savings", 0)
    current   = assumptions.get("current_savings", 0)
    gap       = outcomes.get("gap_amount", 0)
    surplus   = outcomes.get("surplus", 0)
    contrib   = outcomes.get("contribution_required", 0)
    months_to = outcomes.get("months_to_goal")

    system_prompt = (
        "You are a financial planning assistant. Explain this goal feasibility "
        "result in plain English. STRICT RULES: "
        "(1) Use ONLY the numbers shown in the user message. "
        "(2) Do NOT predict market returns or add numbers not listed. "
        "(3) Write exactly 3-5 sentences. "
        "(4) Address the user directly. "
        "(5) Be direct about whether the goal is achievable."
    )
    months_to_str = f"{months_to} months" if months_to else "not within the horizon"
    user_content = (
        f"Goal feasibility result:\nGoal type: {goal_type}\n"
        f"Target amount: Rs.{target:,.0f}\nHorizon: {horizon} months\n"
        f"Current savings: Rs.{current:,.0f}\nMonthly savings: Rs.{monthly:,.0f}/month\n"
        f"Result: {label}\n"
        f"Projected balance at end: Rs.{outcomes.get('projected_balance', 0):,.0f}\n"
        f"Gap (if any): Rs.{gap:,.0f}\nSurplus (if any): Rs.{surplus:,.0f}\n"
        f"Months to reach goal: {months_to_str}\n"
        f"Monthly contribution required to reach goal: Rs.{contrib:,.0f}\n"
    )

    msg = ""
    try:
        async with httpx.AsyncClient(timeout=GROQ_TIMEOUT_S) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL,
                      "messages": [{"role": "system", "content": system_prompt},
                                   {"role": "user", "content": user_content}],
                      "temperature": 0.2, "max_tokens": 300},
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()

            latency_ms        = round((time.perf_counter() - t0) * 1000, 1)
            usage             = resp.json().get("usage", {})
            prompt_tokens     = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            from app.agents.ops_logger import log_llm_call
            log_llm_call("goal", GROQ_MODEL, prompt_tokens, completion_tokens, latency_ms)
            log_node_end("goal_explain", "goal", latency_ms, "success",
                         {"explanation_length_chars": len(raw)})

            try:
                from app.agents.mlflow_tracker import track_llm_call
                track_llm_call("goal", GROQ_MODEL, prompt_tokens, completion_tokens,
                               latency_ms, user_content[:500], raw)
            except Exception: pass
            try:
                from app.metrics import llm_latency, token_counter, node_duration
                llm_latency.labels("goal").observe(latency_ms / 1000)
                token_counter.labels("prompt").inc(prompt_tokens)
                token_counter.labels("completion").inc(completion_tokens)
                node_duration.labels("goal_explain", "goal").observe(latency_ms / 1000)
            except Exception: pass

        logger.info("goal_explain: LLM OK (%d chars)", len(raw))
        return {**state, "graph_trace": trace, "llm_explanation": raw}

    except httpx.TimeoutException:
        msg = f"Groq timed out after {GROQ_TIMEOUT_S}s"
        logger.warning("goal_explain: %s", msg)
    except httpx.HTTPStatusError as exc:
        try:    error_body = exc.response.text
        except Exception: error_body = "(could not read response body)"
        msg = f"Groq HTTP {exc.response.status_code}: {error_body}"
        logger.error("goal_explain: %s", msg)
    except Exception as exc:
        msg = f"Groq call failed: {type(exc).__name__}: {exc}"
        logger.error("goal_explain: %s", msg)

    log_node_end("goal_explain", "goal",
                 round((time.perf_counter() - t0) * 1000, 1), "fallback",
                 {"llm_failed": True})
    return {**state, **mark_degraded(state, msg),
            "graph_trace": trace, "llm_explanation": None}


# ===========================================================================
# NODE 5 — goal_filter
# ===========================================================================

def goal_filter(state: VaultAIState) -> VaultAIState:
    trace    = append_trace(state, "goal_filter")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("goal_filter", "goal", list(state.keys()))
    t0 = time.perf_counter()

    raw      = state.get("llm_explanation")
    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}

    if raw is None:
        filtered = _build_deterministic_summary(outcomes, assum)
        logger.info("goal_filter: LLM was None — deterministic summary used")
    else:
        from app.agents.filters.llm_output_filter import filter_llm_output
        result   = filter_llm_output(raw, outcomes, assum)
        filtered = result.text_clean
        logger.info("goal_filter: %d→%d chars", len(raw), len(filtered))

    log_node_end("goal_filter", "goal",
                 round((time.perf_counter() - t0) * 1000, 1), "success",
                 {"output_length": len(filtered)})

    return {**state, "graph_trace": trace, "explanation_filtered": filtered}


# ===========================================================================
# NODE 6 — goal_fallback
# ===========================================================================

def goal_fallback(state: VaultAIState) -> VaultAIState:
    trace    = append_trace(state, "goal_fallback")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("goal_fallback", "goal", list(state.keys()))
    t0 = time.perf_counter()

    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}
    errors   = state.get("validation_errors") or ["validation failed"]
    reason   = errors[0]

    summary = (_build_deterministic_summary(outcomes, assum) if outcomes
               else ("Unable to generate a goal plan: simulation results could not be "
                     "validated. Please try again or contact support."))

    try:
        from app.metrics import plan_counter, execution_state_counter
        plan_counter.labels("goal", "degraded").inc()
        execution_state_counter.labels("goal", "fallback").inc()
    except Exception: pass

    log_node_end("goal_fallback", "goal",
                 round((time.perf_counter() - t0) * 1000, 1), "fallback",
                 {"reason": reason[:200]})

    logger.warning("goal_fallback: degraded — %s", reason)
    return {**state, **mark_degraded(state, reason),
            "graph_trace": trace, "explanation_filtered": summary}