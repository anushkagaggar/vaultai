"""
VaultAI V3 — agents/invest/nodes.py
=====================================
Full implementations for every node in the invest agent subgraph.

Wire into graph.py with:

    from app.agents.invest.nodes import (
        invest_fetch_data,
        invest_allocate,
        invest_validate,
        invest_explain,
        invest_filter,
        invest_fallback,
    )

Async/sync split:
    async  invest_fetch_data  — awaits build_trends_report() DB call
    sync   invest_allocate    — pure deterministic template math
    sync   invest_validate    — pure re-run math (checkpoint)
    async  invest_explain     — awaits Groq HTTP call
    sync   invest_filter      — string scrubbing
    sync   invest_fallback    — template build

INVEST AGENT DESIGN
--------------------
Unlike budget, invest has NO external market API in Phase 4.
Alpha Vantage / FRED integration is Phase 5.

For now invest_fetch_data loads V2 spending analytics (same as budget)
so invest_allocate knows the user's monthly cash flow. External market
data is hardcoded as conservative fallback rates, and
external_freshness is set to FALLBACK always.

invest_allocate applies a deterministic risk-profile → allocation
template. Risk profiles:

    conservative:  equity=20%, debt=60%, liquid=20%
    moderate:      equity=50%, debt=30%, liquid=20%
    aggressive:    equity=75%, debt=15%, liquid=10%

GUARDRAIL: invest_explain NEVER receives raw price data or historical
returns. It receives only the allocation percentages and the risk-free
rate. This is enforced by what we put in the LLM prompt.

Author: VaultAI V3
"""

from __future__ import annotations

import logging
import os
import re

import httpx

from app.agents.State import (
    VaultAIState,
    ValidationStatus,
    ExternalFreshness,
    append_trace,
    get_v2_analytics,
    mark_degraded,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROQ_API_URL        = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL          = "llama-3.1-8b-instant"
GROQ_TIMEOUT_S      = 15

# Risk-profile → allocation template
# equity_pct, debt_pct, liquid_pct must sum to 100
ALLOCATION_TEMPLATES: dict[str, dict] = {
    "conservative": {"equity_pct": 20.0, "debt_pct": 60.0, "liquid_pct": 20.0},
    "moderate":     {"equity_pct": 50.0, "debt_pct": 30.0, "liquid_pct": 20.0},
    "aggressive":   {"equity_pct": 75.0, "debt_pct": 15.0, "liquid_pct": 10.0},
}
DEFAULT_RISK_PROFILE = "moderate"

# Hardcoded fallback rates used when no external market API is available.
# Conservative estimates — never passed to LLM directly.
FALLBACK_RATES = {
    "equity_annual_return_pct":   12.0,   # Nifty 50 long-run average (India)
    "debt_annual_return_pct":      7.0,   # Conservative gilt/FD rate
    "liquid_annual_return_pct":    5.5,   # Liquid fund / savings account
    "inflation_pct":               6.0,
    "risk_free_rate_pct":          6.5,   # RBI repo rate proxy
}

# Tolerance for allocation percentage sum validation (should be exactly 100)
ALLOCATION_SUM_TOLERANCE = 0.01

_SPECULATIVE_RE = re.compile(
    r"\b(might|may|could|perhaps|possibly|around|approximately|"
    r"up to|somewhere between|you should consider|expected to)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_trends_report(report: dict) -> None:
    """Raise ValueError if the V2 analytics dict is missing required keys."""
    for key in ("rolling", "monthly", "trend_type", "categories"):
        if key not in report:
            raise ValueError(f"V2 analytics missing required key: '{key}'")


def _compute_investable_surplus(analytics: dict, req_params: dict) -> float:
    """
    Estimate monthly investable surplus from V2 analytics.

    If income_monthly is provided in request_params, use it.
    Otherwise fall back to: income_monthly = 0 (pure amount-based invest).

    Returns the monthly amount available for investment.
    """
    income = float(req_params.get("income_monthly", 0))
    rolling = analytics.get("rolling", {})
    monthly_spend = round(
        float(rolling.get("90_day_avg") or rolling.get("30_day_avg") or 0) / 3.0, 2
    )
    if income > 0:
        return round(max(0.0, income - monthly_spend), 2)
    return 0.0


def _resolve_risk_profile(req_params: dict) -> str:
    """Return validated risk profile string, defaulting to moderate."""
    profile = str(req_params.get("risk_profile", DEFAULT_RISK_PROFILE)).lower().strip()
    if profile not in ALLOCATION_TEMPLATES:
        logger.warning(
            "invest_allocate: unknown risk_profile '%s' — using '%s'",
            profile, DEFAULT_RISK_PROFILE,
        )
        return DEFAULT_RISK_PROFILE
    return profile


def _build_deterministic_summary(outcomes: dict, assumptions: dict) -> str:
    """Plain-text invest summary — no LLM."""
    amount    = assumptions.get("investment_amount", 0)
    profile   = assumptions.get("risk_profile", "moderate")
    horizon   = assumptions.get("horizon_months", 0)
    equity    = outcomes.get("equity_pct", 0)
    debt      = outcomes.get("debt_pct", 0)
    liquid    = outcomes.get("liquid_pct", 0)
    eq_amt    = outcomes.get("equity_amount", 0)
    debt_amt  = outcomes.get("debt_amount", 0)
    liq_amt   = outcomes.get("liquid_amount", 0)

    return (
        f"Based on your {profile} risk profile, your Rs.{amount:,.0f} investment "
        f"over {horizon} months is allocated as follows: "
        f"Equity Rs.{eq_amt:,.0f} ({equity:.0f}%), "
        f"Debt Rs.{debt_amt:,.0f} ({debt:.0f}%), "
        f"Liquid Rs.{liq_amt:,.0f} ({liquid:.0f}%). "
        f"This allocation is deterministic and based on your stated risk tolerance."
    )


# ===========================================================================
# NODE 1 — invest_fetch_data  (async: DB I/O)
# ===========================================================================

async def invest_fetch_data(state: VaultAIState) -> VaultAIState:
    """
    Loads V2 spending analytics for cash-flow context.
    Sets external_data to hardcoded fallback rates (Phase 4 — no live API).
    Sets external_freshness = FALLBACK always in Phase 4.

    Resolution order for V2 analytics:
      1. request_params["_v2_analytics"] — pre-fetched by route handler
      2. request_params["_db"]           — live AsyncSession

    Writes: v2_analytics, v2_expenses, external_data, external_freshness,
            graph_trace, audit_payload
    """
    trace      = append_trace(state, "invest_fetch_data")
    user_id    = state["user_id"]
    req_params = state.get("request_params", {})

    analytics_result: dict | None = None
    load_error: str | None        = None

    if "_v2_analytics" in req_params:
        analytics_result = req_params["_v2_analytics"]

    elif "_db" in req_params:
        try:
            from app.analytics.trends import build_trends_report
            analytics_result = await build_trends_report(
                req_params["_db"], int(user_id)
            )
        except Exception as exc:
            load_error = f"build_trends_report() raised {type(exc).__name__}: {exc}"
            logger.error("invest_fetch_data: %s", load_error)

    else:
        load_error = (
            "invest_fetch_data requires request_params['_v2_analytics'] "
            "or request_params['_db']. Neither was found."
        )

    if load_error is None and analytics_result is None:
        load_error = f"build_trends_report() returned None for user_id={user_id}"

    if load_error is None:
        try:
            _validate_trends_report(analytics_result)
        except ValueError as exc:
            load_error = str(exc)

    if load_error is not None:
        logger.error("invest_fetch_data: DEPENDENCY_UNAVAILABLE — %s", load_error)
        raise RuntimeError(f"invest_fetch_data failed: {load_error}")

    # Phase 4: always use hardcoded fallback rates — no live API
    external_data = {**FALLBACK_RATES, "source": "hardcoded_phase4_fallback"}

    existing_payload = state.get("audit_payload") or {}
    load_metrics = {
        "data_days_available": 90 if analytics_result.get("rolling", {}).get("90_day_avg") else 30,
        "external_data_source": "fallback",
    }

    logger.info(
        "invest_fetch_data: OK — V2 analytics loaded, external_data=fallback "
        "(live market API coming Phase 5)"
    )

    return {
        **state,
        "v2_analytics":      analytics_result,
        "v2_expenses":       [],
        "external_data":     external_data,
        "external_freshness": ExternalFreshness.FALLBACK,
        "graph_trace":       trace,
        "audit_payload":     {**existing_payload, "invest_load_metrics": load_metrics},
        "degraded":          True,   # FALLBACK external data always sets degraded
    }


# ===========================================================================
# NODE 2 — invest_allocate  (sync: pure template math)
# ===========================================================================

def invest_allocate(state: VaultAIState) -> VaultAIState:
    """
    Applies deterministic risk-profile → allocation template.

    Required in request_params:
        investment_amount   float  — lump sum to allocate
        risk_profile        str    — "conservative" | "moderate" | "aggressive"

    Optional in request_params:
        horizon_months      int    — investment horizon (default 36)
        income_monthly      float  — used to compute investable surplus

    Writes: projected_outcomes, assumptions, constraints
    """
    trace      = append_trace(state, "invest_allocate")
    req_params = state.get("request_params", {})

    # ── Investment amount (required) ──────────────────────────────────────
    amount_raw = req_params.get("investment_amount")
    if not amount_raw:
        raise ValueError(
            "investment_amount is required in request_params for an invest plan."
        )
    amount = float(amount_raw)

    risk_profile = _resolve_risk_profile(req_params)
    horizon      = int(req_params.get("horizon_months", 36))
    template     = ALLOCATION_TEMPLATES[risk_profile]

    equity_pct  = template["equity_pct"]
    debt_pct    = template["debt_pct"]
    liquid_pct  = template["liquid_pct"]

    equity_amt  = round(amount * equity_pct / 100, 2)
    debt_amt    = round(amount * debt_pct   / 100, 2)
    liquid_amt  = round(amount - equity_amt - debt_amt, 2)  # avoids rounding gap

    # Investable surplus from V2 analytics (informational, not used in allocation)
    analytics = state.get("v2_analytics") or {}
    monthly_surplus = _compute_investable_surplus(analytics, req_params)

    logger.info(
        "invest_allocate: amount=%.0f profile=%s "
        "equity=%.0f%% debt=%.0f%% liquid=%.0f%%",
        amount, risk_profile, equity_pct, debt_pct, liquid_pct,
    )

    # Constraints stored verbatim for invest_validate to re-run identically
    constraints = {
        "investment_amount": amount,
        "risk_profile":      risk_profile,
        "template":          template,
    }

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
            "rates_source":       "hardcoded_fallback",
            "risk_free_rate_pct": FALLBACK_RATES["risk_free_rate_pct"],
        },
        "constraints": constraints,
    }


# ===========================================================================
# NODE 3 — invest_validate  (sync: checkpoint)
# ===========================================================================

def invest_validate(state: VaultAIState) -> VaultAIState:
    """
    CHECKPOINT — re-applies the allocation template with the exact inputs
    stored in state["constraints"] and asserts:
      1. equity + debt + liquid == 100% (within tolerance)
      2. allocation matches the stored template for the risk profile
      3. amounts sum to investment_amount (within tolerance)

    PASSED → graph routes to invest_explain
    FAILED → graph routes to invest_fallback
    """
    trace   = append_trace(state, "invest_validate")
    stored  = state.get("projected_outcomes")
    cons    = state.get("constraints")

    if stored is None or cons is None:
        reason = "projected_outcomes or constraints missing — invest_allocate did not run"
        logger.error("invest_validate: %s", reason)
        degraded_patch = mark_degraded(state, reason)
        return {
            **state, **degraded_patch,
            "graph_trace":       trace,
            "validation_status": ValidationStatus.FAILED,
            "validation_errors": [reason],
        }

    errors: list[str] = []

    # ── Check 1: percentages sum to 100 ──────────────────────────────────
    pct_sum = stored.get("equity_pct", 0) + stored.get("debt_pct", 0) + stored.get("liquid_pct", 0)
    if abs(pct_sum - 100.0) > ALLOCATION_SUM_TOLERANCE:
        errors.append(
            f"allocation percentages sum to {pct_sum:.4f}, expected 100.0"
        )

    # ── Check 2: percentages match the stored template ────────────────────
    profile  = cons.get("risk_profile", DEFAULT_RISK_PROFILE)
    template = ALLOCATION_TEMPLATES.get(profile, ALLOCATION_TEMPLATES[DEFAULT_RISK_PROFILE])

    for key in ("equity_pct", "debt_pct", "liquid_pct"):
        stored_val   = stored.get(key, 0)
        expected_val = template[key.replace("_pct", "_pct")]  # same key
        if abs(stored_val - expected_val) > ALLOCATION_SUM_TOLERANCE:
            errors.append(
                f"{key} mismatch: stored={stored_val}, "
                f"expected={expected_val} for profile={profile}"
            )

    # ── Check 3: amounts sum to investment_amount ─────────────────────────
    amount      = cons.get("investment_amount", 0)
    total_alloc = stored.get("total_allocated", 0)
    if abs(total_alloc - amount) > 1.0:   # 1 rupee tolerance for rounding
        errors.append(
            f"total_allocated={total_alloc} != investment_amount={amount}"
        )

    if errors:
        logger.warning("invest_validate: FAILED — %s", errors)
        degraded_patch = mark_degraded(state, "; ".join(errors))
        return {
            **state, **degraded_patch,
            "graph_trace":       trace,
            "validation_status": ValidationStatus.FAILED,
            "validation_errors": errors,
        }

    logger.info("invest_validate: PASSED")
    return {
        **state,
        "graph_trace":       trace,
        "validation_status": ValidationStatus.PASSED,
        "validation_errors": [],
    }


# ===========================================================================
# NODE 4 — invest_explain  (async: Groq HTTP I/O)
# ===========================================================================

async def invest_explain(state: VaultAIState) -> VaultAIState:
    """
    Calls Groq LLM to narrate the allocation in plain English.

    GUARDRAIL: prompt contains ONLY allocation percentages, amounts,
    risk profile, and risk-free rate. Raw price data from external_data
    is NEVER passed to the LLM. This is enforced here, not by the LLM.

    On any error → llm_explanation = None, invest_filter uses deterministic summary.
    """
    trace       = append_trace(state, "invest_explain")
    outcomes    = state.get("projected_outcomes") or {}
    assumptions = state.get("assumptions") or {}

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("invest_explain: GROQ_API_KEY not set — skipping LLM")
        degraded_patch = mark_degraded(state, "GROQ_API_KEY not configured")
        return {**state, **degraded_patch, "graph_trace": trace, "llm_explanation": None}

    profile    = outcomes.get("risk_profile", "moderate")
    amount     = assumptions.get("investment_amount", 0)
    horizon    = assumptions.get("horizon_months", 36)
    rfr        = assumptions.get("risk_free_rate_pct", 6.5)

    system_prompt = (
        "You are a financial planning assistant. Explain this investment allocation "
        "in plain English. STRICT RULES: "
        "(1) Use ONLY the numbers shown in the user message. "
        "(2) Do NOT mention historical returns, market predictions, or price forecasts. "
        "(3) Do NOT speculate about future performance. "
        "(4) Write exactly 3-5 sentences. "
        "(5) Address the user directly."
    )
    user_content = (
        f"Investment allocation:\n"
        f"Total amount: Rs.{amount:,.0f}\n"
        f"Risk profile: {profile}\n"
        f"Investment horizon: {horizon} months\n"
        f"Risk-free rate: {rfr:.1f}%\n\n"
        f"Allocation:\n"
        f"  Equity: {outcomes.get('equity_pct', 0):.0f}% "
        f"(Rs.{outcomes.get('equity_amount', 0):,.0f})\n"
        f"  Debt:   {outcomes.get('debt_pct', 0):.0f}% "
        f"(Rs.{outcomes.get('debt_amount', 0):,.0f})\n"
        f"  Liquid: {outcomes.get('liquid_pct', 0):.0f}% "
        f"(Rs.{outcomes.get('liquid_amount', 0):,.0f})\n"
    )

    msg = ""
    try:
        async with httpx.AsyncClient(timeout=GROQ_TIMEOUT_S) as client:
            resp = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={
                    "model":       GROQ_MODEL,
                    "messages":    [{"role": "system", "content": system_prompt},
                                    {"role": "user",   "content": user_content}],
                    "temperature": 0.2,
                    "max_tokens":  300,
                },
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
        logger.info("invest_explain: LLM OK (%d chars)", len(raw))
        return {**state, "graph_trace": trace, "llm_explanation": raw}

    except httpx.TimeoutException:
        msg = f"Groq timed out after {GROQ_TIMEOUT_S}s"
        logger.warning("invest_explain: %s", msg)
    except httpx.HTTPStatusError as exc:
        # Log the full Groq error body so we know exactly what's wrong
        try:
            error_body = exc.response.text
        except Exception:
            error_body = "(could not read response body)"
        msg = f"Groq HTTP {exc.response.status_code}: {error_body}"
        logger.error("invest_explain: %s", msg)
    except Exception as exc:
        msg = f"Groq call failed: {type(exc).__name__}: {exc}"
        logger.error("invest_explain: %s", msg)

    degraded_patch = mark_degraded(state, msg)
    return {**state, **degraded_patch, "graph_trace": trace, "llm_explanation": None}


# ===========================================================================
# NODE 5 — invest_filter  (sync: string scrubbing)
# ===========================================================================

def invest_filter(state: VaultAIState) -> VaultAIState:
    """
    Scrubs llm_explanation and writes explanation_filtered.

    Invest-specific forbidden patterns (beyond budget's list):
      - Any mention of predicted returns ("expected to return", "will grow to")
      - Percentage gains without explicit qualifier

    If llm_explanation is None → deterministic summary.
    """
    trace    = append_trace(state, "invest_filter")
    raw      = state.get("llm_explanation")
    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}

    if raw is None:
        filtered = _build_deterministic_summary(outcomes, assum)
        logger.info("invest_filter: LLM was None — deterministic summary used")
    else:
        filtered = _SPECULATIVE_RE.sub("", raw)
        # Invest-specific: strip "will return X%" / "expected return of X%"
        filtered = re.sub(
            r"\b(will return|expected return of|projected return)\s+[\d.]+\s*%",
            "",
            filtered,
            flags=re.IGNORECASE,
        )
        filtered = re.sub(r"  +", " ", filtered).strip()
        logger.info("invest_filter: scrubbed %d→%d chars", len(raw), len(filtered))

    return {**state, "graph_trace": trace, "explanation_filtered": filtered}


# ===========================================================================
# NODE 6 — invest_fallback  (sync: template build)
# ===========================================================================

def invest_fallback(state: VaultAIState) -> VaultAIState:
    """
    Reached when invest_validate returns FAILED.
    Builds deterministic summary, marks degraded, skips LLM.
    """
    trace    = append_trace(state, "invest_fallback")
    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}
    errors   = state.get("validation_errors") or ["validation failed"]
    reason   = errors[0]

    degraded_patch = mark_degraded(state, reason)
    summary = (
        _build_deterministic_summary(outcomes, assum)
        if outcomes
        else (
            "Unable to generate an investment plan: allocation could not be "
            "validated. Please try again or contact support."
        )
    )

    logger.warning("invest_fallback: degraded — %s", reason)
    return {
        **state, **degraded_patch,
        "graph_trace":          trace,
        "explanation_filtered": summary,
    }