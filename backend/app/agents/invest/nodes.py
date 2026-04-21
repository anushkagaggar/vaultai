"""
VaultAI V3 — agents/invest/nodes.py   [LLMOps instrumented]
============================================================
LLMOps changes only — all business logic unchanged.
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
    ExternalFreshness,
    append_trace,
    mark_degraded,
    get_v2_analytics,
)
from app.integrations.market_api import fetch_market_context, MarketContext

logger = logging.getLogger(__name__)

GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL     = "llama-3.1-8b-instant"
GROQ_TIMEOUT_S = 15

ALLOCATION_TEMPLATES: dict[str, dict] = {
    "conservative": {"equity_pct": 20.0, "debt_pct": 60.0, "liquid_pct": 20.0},
    "moderate":     {"equity_pct": 50.0, "debt_pct": 35.0, "liquid_pct": 15.0},
    "aggressive":   {"equity_pct": 75.0, "debt_pct": 15.0, "liquid_pct": 10.0},
}
DEFAULT_RISK_PROFILE  = "moderate"
ALLOCATION_SUM_TARGET = 100.0
ALLOCATION_SUM_TOL    = 0.01

_SPECULATIVE_RE = re.compile(
    r"\b(might|may|could|perhaps|possibly|around|approximately|"
    r"up to|somewhere between|you should consider|expected to|"
    r"will return|projected return|expected return)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers (unchanged)
# ---------------------------------------------------------------------------

def _validate_trends_report(report: dict) -> None:
    for key in ("rolling", "monthly", "trend_type", "categories"):
        if key not in report:
            raise ValueError(f"V2 analytics missing required key: '{key}'")


def _freshness_to_enum(freshness_str: str) -> ExternalFreshness:
    return {"live": ExternalFreshness.LIVE,
            "cached": ExternalFreshness.CACHED,
            "fallback": ExternalFreshness.FALLBACK}.get(
        freshness_str, ExternalFreshness.FALLBACK)


def _resolve_risk_profile(req_params: dict) -> str:
    profile = str(req_params.get("risk_profile", DEFAULT_RISK_PROFILE)).lower().strip()
    valid = set(ALLOCATION_TEMPLATES.keys()) | {"custom"}
    if profile not in valid:
        logger.warning("invest_allocate: unknown risk_profile '%s' — using '%s'",
                       profile, DEFAULT_RISK_PROFILE)
        return DEFAULT_RISK_PROFILE
    return profile


def _get_custom_allocation(req_params: dict) -> dict:
    equity = float(req_params.get("custom_equity_pct", 0))
    debt   = float(req_params.get("custom_debt_pct", 0))
    liquid = float(req_params.get("custom_liquid_pct", 0))
    total  = equity + debt + liquid
    if abs(total - ALLOCATION_SUM_TARGET) > ALLOCATION_SUM_TOL:
        raise ValueError(
            f"Custom allocation percentages must sum to 100%. "
            f"Got equity={equity}% + debt={debt}% + liquid={liquid}% = {total:.4f}%.")
    return {"equity_pct": equity, "debt_pct": debt, "liquid_pct": liquid}


def _compute_investable_surplus(analytics: dict, req_params: dict) -> float:
    income = float(req_params.get("income_monthly", 0))
    rolling = analytics.get("rolling", {})
    monthly_spend = round(
        float(rolling.get("90_day_avg") or rolling.get("30_day_avg") or 0) / 3.0, 2)
    if income > 0:
        return round(max(0.0, income - monthly_spend), 2)
    return 0.0


def _build_deterministic_summary(outcomes: dict, assumptions: dict) -> str:
    amount   = assumptions.get("investment_amount", 0)
    profile  = assumptions.get("risk_profile", "moderate")
    horizon  = assumptions.get("horizon_months", 0)
    equity   = outcomes.get("equity_pct", 0)
    debt     = outcomes.get("debt_pct", 0)
    liquid   = outcomes.get("liquid_pct", 0)
    eq_amt   = outcomes.get("equity_amount", 0)
    debt_amt = outcomes.get("debt_amount", 0)
    liq_amt  = outcomes.get("liquid_amount", 0)
    rfr      = assumptions.get("risk_free_rate_pct", 6.5)
    return (
        f"Based on your {profile} risk profile, your Rs.{amount:,.0f} investment "
        f"over {horizon} months is allocated as follows: "
        f"Equity Rs.{eq_amt:,.0f} ({equity:.0f}%), "
        f"Debt Rs.{debt_amt:,.0f} ({debt:.0f}%), "
        f"Liquid Rs.{liq_amt:,.0f} ({liquid:.0f}%). "
        f"The current risk-free rate is {rfr:.1f}%. "
        f"This allocation reflects your stated risk tolerance."
    )


# ===========================================================================
# NODE 1 — invest_fetch_data
# ===========================================================================

async def invest_fetch_data(state: VaultAIState) -> VaultAIState:
    trace      = append_trace(state, "invest_fetch_data")
    user_id    = state["user_id"]
    req_params = state.get("request_params", {})

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("invest_fetch_data", "invest", list(state.keys()))
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
            logger.error("invest_fetch_data: %s", load_error)
    else:
        load_error = ("invest_fetch_data requires request_params['_v2_analytics'] "
                      "or request_params['_db']. Neither found.")

    if load_error is None and analytics_result is None:
        load_error = f"build_trends_report() returned None for user_id={user_id}"
    if load_error is None:
        try: _validate_trends_report(analytics_result)
        except ValueError as exc: load_error = str(exc)

    if load_error is not None:
        raise RuntimeError(f"invest_fetch_data: V2 analytics failed — {load_error}")

    market: MarketContext = await fetch_market_context()
    freshness_enum = _freshness_to_enum(market.freshness)
    is_degraded    = (freshness_enum == ExternalFreshness.FALLBACK)
    existing_payload = state.get("audit_payload") or {}

    log_node_end("invest_fetch_data", "invest",
                 round((time.perf_counter() - t0) * 1000, 1), "success",
                 {"market_freshness": market.freshness,
                  "risk_free_rate_pct": market.risk_free_rate_pct})

    logger.info("invest_fetch_data: OK — V2 loaded, market freshness=%s rfr=%.2f%%",
                market.freshness, market.risk_free_rate_pct)

    return {
        **state,
        "v2_analytics":       analytics_result,
        "v2_expenses":        [],
        "external_data":      market.to_audit_dict(),
        "external_freshness": freshness_enum,
        "graph_trace":        trace,
        "degraded":           is_degraded,
        "audit_payload":      {
            **existing_payload,
            "v2_load_metrics": {
                "data_days_available": (
                    90 if analytics_result.get("rolling", {}).get("90_day_avg") else 30
                ),
            },
            "market_context": market.to_audit_dict(),
        },
    }


# ===========================================================================
# NODE 2 — invest_allocate
# ===========================================================================

def invest_allocate(state: VaultAIState) -> VaultAIState:
    trace      = append_trace(state, "invest_allocate")
    req_params = state.get("request_params", {})

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("invest_allocate", "invest", list(state.keys()))
    t0 = time.perf_counter()

    amount_raw = req_params.get("investment_amount")
    if not amount_raw:
        raise ValueError("investment_amount is required in request_params.")
    amount = float(amount_raw)

    risk_profile = _resolve_risk_profile(req_params)
    horizon      = int(req_params.get("horizon_months", 36))

    template   = _get_custom_allocation(req_params) if risk_profile == "custom" \
                 else ALLOCATION_TEMPLATES[risk_profile]
    equity_pct = template["equity_pct"]
    debt_pct   = template["debt_pct"]
    liquid_pct = template["liquid_pct"]

    equity_amt = round(amount * equity_pct / 100, 2)
    debt_amt   = round(amount * debt_pct   / 100, 2)
    liquid_amt = round(amount - equity_amt - debt_amt, 2)

    external_data  = state.get("external_data") or {}
    risk_free_rate = float(external_data.get("risk_free_rate_pct", 6.5))
    inflation      = float(external_data.get("inflation_pct", 5.5))

    analytics       = state.get("v2_analytics") or {}
    monthly_surplus = _compute_investable_surplus(analytics, req_params)

    duration_ms  = round((time.perf_counter() - t0) * 1000, 1)
    node_metrics = {"equity_pct": equity_pct, "debt_pct": debt_pct,
                    "liquid_pct": liquid_pct,
                    "total_allocated": round(equity_amt + debt_amt + liquid_amt, 2),
                    "risk_free_rate_pct": risk_free_rate}

    log_node_end("invest_allocate", "invest", duration_ms, "success", node_metrics)

    try:
        from app.agents.mlflow_tracker import track_agent_node
        track_agent_node("invest_allocate", "invest", duration_ms, "success", node_metrics)
    except Exception:
        pass

    try:
        from app.metrics import node_duration, plan_counter
        node_duration.labels("invest_allocate", "invest").observe(duration_ms / 1000)
        plan_counter.labels("invest", "success").inc()
    except Exception:
        pass

    logger.info("invest_allocate: amount=%.0f profile=%s equity=%.1f%% rfr=%.2f%%",
                amount, risk_profile, equity_pct, risk_free_rate)

    constraints = {"investment_amount": amount, "risk_profile": risk_profile,
                   "template": template,
                   "equity_pct": equity_pct, "debt_pct": debt_pct, "liquid_pct": liquid_pct}

    return {
        **state,
        "graph_trace": trace,
        "projected_outcomes": {
            "equity_pct":        equity_pct,
            "debt_pct":          debt_pct,
            "liquid_pct":        liquid_pct,
            "equity_amount":     equity_amt,
            "debt_amount":       debt_amt,
            "liquid_amount":     liquid_amt,
            "total_allocated":   round(equity_amt + debt_amt + liquid_amt, 2),
            "risk_profile":      risk_profile,
            "allocation_method": "deterministic_template",
        },
        "assumptions": {
            "investment_amount":  amount,
            "risk_profile":       risk_profile,
            "horizon_months":     horizon,
            "monthly_surplus":    monthly_surplus,
            "risk_free_rate_pct": risk_free_rate,
            "inflation_pct":      inflation,
        },
        "constraints": constraints,
    }


# ===========================================================================
# NODE 3 — invest_validate
# ===========================================================================

def invest_validate(state: VaultAIState) -> VaultAIState:
    trace  = append_trace(state, "invest_validate")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("invest_validate", "invest", list(state.keys()))
    t0 = time.perf_counter()

    stored = state.get("projected_outcomes")
    cons   = state.get("constraints")

    if stored is None or cons is None:
        reason = "projected_outcomes or constraints missing — invest_allocate did not run"
        logger.error("invest_validate: %s", reason)
        log_node_end("invest_validate", "invest",
                     round((time.perf_counter() - t0) * 1000, 1), "failed",
                     {"validation_passed": False})
        return {**state, **mark_degraded(state, reason),
                "graph_trace": trace,
                "validation_status": ValidationStatus.FAILED,
                "validation_errors": [reason]}

    errors: list[str] = []
    pct_sum = (stored.get("equity_pct", 0) + stored.get("debt_pct", 0)
               + stored.get("liquid_pct", 0))
    if abs(pct_sum - ALLOCATION_SUM_TARGET) > ALLOCATION_SUM_TOL:
        errors.append(f"percentages sum to {pct_sum:.6f}%, must be 100%")
    for key in ("equity_pct", "debt_pct", "liquid_pct"):
        sv = float(stored.get(key, 0))
        cv = float(cons.get(key, 0))
        if abs(sv - cv) > ALLOCATION_SUM_TOL:
            errors.append(f"{key}: stored={sv:.4f}% != constraint={cv:.4f}%")
    amount      = float(cons.get("investment_amount", 0))
    total_alloc = float(stored.get("total_allocated", 0))
    if abs(total_alloc - amount) > 1.0:
        errors.append(f"total_allocated={total_alloc:.2f} != investment_amount={amount:.2f}")

    duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    passed = not errors

    log_node_end("invest_validate", "invest", duration_ms,
                 "success" if passed else "failed",
                 {"validation_passed": passed, "pct_sum": pct_sum})

    try:
        from app.agents.mlflow_tracker import track_agent_node
        track_agent_node("invest_validate", "invest", duration_ms,
                         "success" if passed else "failed",
                         {"validation_passed": float(passed), "pct_sum": pct_sum})
    except Exception:
        pass

    if errors:
        logger.warning("invest_validate: FAILED — %s", errors)
        return {**state, **mark_degraded(state, errors[0]),
                "graph_trace": trace,
                "validation_status": ValidationStatus.FAILED,
                "validation_errors": errors}

    logger.info("invest_validate: PASSED — sum=%.4f%% total=%.2f", pct_sum, total_alloc)
    return {**state,
            "graph_trace":       trace,
            "validation_status": ValidationStatus.PASSED,
            "validation_errors": []}


# ===========================================================================
# NODE 4 — invest_explain
# ===========================================================================

async def invest_explain(state: VaultAIState) -> VaultAIState:
    trace       = append_trace(state, "invest_explain")
    outcomes    = state.get("projected_outcomes") or {}
    assumptions = state.get("assumptions") or {}

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("invest_explain", "invest", list(state.keys()))
    t0 = time.perf_counter()

    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("invest_explain: GROQ_API_KEY not set — skipping LLM")
        log_node_end("invest_explain", "invest",
                     round((time.perf_counter() - t0) * 1000, 1), "fallback",
                     {"llm_skipped": True})
        return {**state, **mark_degraded(state, "GROQ_API_KEY not configured"),
                "graph_trace": trace, "llm_explanation": None}

    profile = outcomes.get("risk_profile", "moderate")
    amount  = assumptions.get("investment_amount", 0)
    horizon = assumptions.get("horizon_months", 36)
    rfr     = assumptions.get("risk_free_rate_pct", 6.5)

    system_prompt = (
        "You are a financial planning assistant. Explain this investment "
        "allocation in plain English. STRICT RULES: "
        "(1) Use ONLY the numbers provided. "
        "(2) Do NOT mention historical returns, market predictions, or future prices. "
        "(3) Do NOT say what returns the user will earn. "
        "(4) Write exactly 3-5 sentences. (5) Address the user directly."
    )
    user_content = (
        f"Investment allocation:\nTotal: Rs.{amount:,.0f}\n"
        f"Risk profile: {profile}\nHorizon: {horizon} months\n"
        f"Risk-free rate: {rfr:.1f}%\n\nAllocation:\n"
        f"  Equity: {outcomes.get('equity_pct', 0):.0f}%"
        f" (Rs.{outcomes.get('equity_amount', 0):,.0f})\n"
        f"  Debt:   {outcomes.get('debt_pct', 0):.0f}%"
        f" (Rs.{outcomes.get('debt_amount', 0):,.0f})\n"
        f"  Liquid: {outcomes.get('liquid_pct', 0):.0f}%"
        f" (Rs.{outcomes.get('liquid_amount', 0):,.0f})\n"
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
            log_llm_call("invest", GROQ_MODEL, prompt_tokens, completion_tokens, latency_ms)
            log_node_end("invest_explain", "invest", latency_ms, "success",
                         {"explanation_length_chars": len(raw)})

            try:
                from app.agents.mlflow_tracker import track_llm_call
                track_llm_call("invest", GROQ_MODEL, prompt_tokens, completion_tokens,
                               latency_ms, user_content[:500], raw)
            except Exception: pass
            try:
                from app.metrics import llm_latency, token_counter, node_duration
                llm_latency.labels("invest").observe(latency_ms / 1000)
                token_counter.labels("prompt").inc(prompt_tokens)
                token_counter.labels("completion").inc(completion_tokens)
                node_duration.labels("invest_explain", "invest").observe(latency_ms / 1000)
            except Exception: pass

        logger.info("invest_explain: LLM OK (%d chars)", len(raw))
        return {**state, "graph_trace": trace, "llm_explanation": raw}

    except httpx.TimeoutException:
        msg = f"Groq timed out after {GROQ_TIMEOUT_S}s"
        logger.warning("invest_explain: %s", msg)
    except httpx.HTTPStatusError as exc:
        try:    error_body = exc.response.text
        except Exception: error_body = "(unreadable)"
        msg = f"Groq HTTP {exc.response.status_code}: {error_body}"
        logger.error("invest_explain: %s", msg)
    except Exception as exc:
        msg = f"Groq error: {type(exc).__name__}: {exc}"
        logger.error("invest_explain: %s", msg)

    log_node_end("invest_explain", "invest",
                 round((time.perf_counter() - t0) * 1000, 1), "fallback",
                 {"llm_failed": True})
    return {**state, **mark_degraded(state, msg),
            "graph_trace": trace, "llm_explanation": None}


# ===========================================================================
# NODE 5 — invest_filter
# ===========================================================================

def invest_filter(state: VaultAIState) -> VaultAIState:
    trace    = append_trace(state, "invest_filter")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("invest_filter", "invest", list(state.keys()))
    t0 = time.perf_counter()

    raw      = state.get("llm_explanation")
    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}

    if raw is None:
        filtered = _build_deterministic_summary(outcomes, assum)
        logger.info("invest_filter: LLM was None — deterministic summary used")
    else:
        try:
            from app.agents.filters.llm_output_filter import filter_llm_output
            result   = filter_llm_output(raw, outcomes, assum)
            filtered = result.text_clean
        except ImportError:
            filtered = _SPECULATIVE_RE.sub("", raw)
            import re as _re
            filtered = _re.sub(r"  +", " ", filtered).strip()
        logger.info("invest_filter: %d→%d chars", len(raw), len(filtered))

    log_node_end("invest_filter", "invest",
                 round((time.perf_counter() - t0) * 1000, 1), "success",
                 {"output_length": len(filtered)})

    return {**state, "graph_trace": trace, "explanation_filtered": filtered}


# ===========================================================================
# NODE 6 — invest_fallback
# ===========================================================================

def invest_fallback(state: VaultAIState) -> VaultAIState:
    trace    = append_trace(state, "invest_fallback")

    from app.agents.ops_logger import log_node_start, log_node_end
    log_node_start("invest_fallback", "invest", list(state.keys()))
    t0 = time.perf_counter()

    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}
    errors   = state.get("validation_errors") or ["validation failed"]

    summary = (_build_deterministic_summary(outcomes, assum) if outcomes
               else "Unable to generate an investment plan. Validation failed.")

    try:
        from app.metrics import plan_counter, execution_state_counter
        plan_counter.labels("invest", "degraded").inc()
        execution_state_counter.labels("invest", "fallback").inc()
    except Exception: pass

    log_node_end("invest_fallback", "invest",
                 round((time.perf_counter() - t0) * 1000, 1), "fallback",
                 {"reason": errors[0][:200]})

    logger.warning("invest_fallback: degraded — %s", errors[0])
    return {**state, **mark_degraded(state, errors[0]),
            "graph_trace": trace, "explanation_filtered": summary}