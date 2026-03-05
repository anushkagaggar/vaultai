"""
VaultAI V3 — agents/goal/nodes.py
===================================
Full implementations for every node in the goal agent subgraph.

Wire into graph.py with:

    from app.agents.goal.nodes import (
        goal_define,
        goal_simulate,
        goal_validate,
        goal_explain,
        goal_filter,
        goal_fallback,
    )

Async/sync split:
    async  goal_define    — awaits build_trends_report() DB call
    sync   goal_simulate  — pure forecast.py math
    sync   goal_validate  — pure re-run math (checkpoint)
    async  goal_explain   — awaits Groq HTTP call
    sync   goal_filter    — string scrubbing
    sync   goal_fallback  — template build

GOAL AGENT DESIGN
------------------
goal_define   parses goal parameters from request_params and loads V2
              spending analytics to determine monthly_savings available.
              Phase 4: also accepts target_date (YYYY-MM-DD) and rejects
              past dates immediately at the schema layer.

goal_simulate calls forecast.goal_feasibility() and
              forecast.contribution_required() for standard goals.
              Phase 4: routes debt_payoff → debt_payoff_schedule(),
              multi_goal → multi_goal_tradeoff(), travel → standard path
              with horizon derived from target_date.
              Returns FEASIBLE / STRETCH / INFEASIBLE label.

goal_validate re-runs the appropriate forecast function with identical
              inputs stored in constraints and asserts the label matches.
              Delegates to agents/goal/checkpoint.py for all goal types.
              A STRETCH or INFEASIBLE result is still PASSED if it matches —
              the checkpoint is about reproducibility, not optimism.

REQUEST PARAMS CONTRACT
------------------------
Required (all goal types):
    goal_type         str    — "savings" | "emergency_fund" | "purchase"
                               | "education" | "retirement"  (Phase 3)
                               | "travel" | "debt_payoff" | "multi_goal"  (Phase 4)
    target_amount     float  — the monetary goal

Required (standard goals):
    horizon_months    int    — months until the target date
    OR
    target_date       str    — YYYY-MM-DD future date (travel goal)

Required (debt_payoff):
    outstanding       float  — current debt balance
    interest_rate     float  — annual interest rate decimal
    monthly_payment   float  — fixed monthly payment

Required (multi_goal):
    sub_goals         list   — 2-5 goal dicts, each with:
                               goal_id, target_amount, horizon_months,
                               current_savings (opt), priority (opt)

Optional (all):
    current_savings   float  — starting balance (default 0)
    annual_rate       float  — expected annual growth rate decimal (default 0.07)
    monthly_savings   float  — fixed monthly contribution
                               if omitted, derived from V2 analytics as
                               income_monthly - monthly_spend
    income_monthly    float  — needed to derive monthly_savings if not given

Author: VaultAI V3
"""

from __future__ import annotations

import logging
import os
import re
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL     = "llama-3.1-8b-instant"
GROQ_TIMEOUT_S = 15

DEFAULT_ANNUAL_RATE = 0.07   # 7% — conservative long-run blended rate

# Phase 3 original types + Phase 4 additions
VALID_GOAL_TYPES = {
    "savings", "emergency_fund", "purchase", "education", "retirement",  # Phase 3
    "travel", "debt_payoff", "multi_goal",                               # Phase 4
}

_SPECULATIVE_RE = re.compile(
    r"\b(might|may|could|perhaps|possibly|around|approximately|"
    r"up to|somewhere between|you should consider|guaranteed)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_trends_report(report: dict) -> None:
    for key in ("rolling", "monthly", "trend_type", "categories"):
        if key not in report:
            raise ValueError(f"V2 analytics missing required key: '{key}'")


def _derive_monthly_savings(analytics: dict, req_params: dict) -> float:
    """
    Derive available monthly savings from V2 analytics + income.

    Priority:
      1. Explicit monthly_savings in request_params
      2. income_monthly - monthly_spend from V2 rolling avg
      3. 0.0 (user has no savings data)
    """
    if "monthly_savings" in req_params:
        return float(req_params["monthly_savings"])

    income = float(req_params.get("income_monthly", 0))
    rolling = analytics.get("rolling", {})
    monthly_spend = round(
        float(rolling.get("90_day_avg") or rolling.get("30_day_avg") or 0) / 3.0, 2
    )
    if income > monthly_spend > 0:
        return round(income - monthly_spend, 2)
    return 0.0


def _horizon_from_target_date(target_date_str: str) -> int:
    """
    Convert a YYYY-MM-DD string to horizon_months.

    Phase 4 exit criterion: raises ValueError if date is in the past.
    Called at goal_define (schema layer) before any simulation runs.
    """
    try:
        target = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"target_date must be YYYY-MM-DD format, got '{target_date_str}'"
        )
    today = date.today()
    if target <= today:
        raise ValueError(
            f"target_date '{target_date_str}' is in the past (today={today}). "
            f"Provide a future date."
        )
    months = (target.year - today.year) * 12 + (target.month - today.month)
    if target.day < today.day:
        months -= 1
    return max(1, months)


def _build_deterministic_summary(outcomes: dict, assumptions: dict) -> str:
    """Plain-text goal summary — no LLM. Preserved from Phase 3."""
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
            return (
                f"Your {goal_type} goal of Rs.{target:,.0f} is achievable. "
                f"At Rs.{monthly_sv:,.0f}/month you will reach it in {months_to} months, "
                f"ahead of your {horizon}-month target."
            )
        return (
            f"Your {goal_type} goal of Rs.{target:,.0f} is achievable. "
            f"Saving Rs.{monthly_sv:,.0f}/month for {horizon} months will reach your target."
        )
    elif label == "STRETCH":
        return (
            f"Your {goal_type} goal of Rs.{target:,.0f} is a stretch. "
            f"You are Rs.{gap:,.0f} short at your current savings rate. "
            f"Increasing to Rs.{contrib:,.0f}/month would make it achievable in {horizon} months."
        )
    else:
        return (
            f"Your {goal_type} goal of Rs.{target:,.0f} is not achievable "
            f"in {horizon} months at your current savings rate. "
            f"You need Rs.{contrib:,.0f}/month to reach this goal. "
            f"Consider extending your timeline or reducing the target amount."
        )


# ===========================================================================
# NODE 1 — goal_define  (async: DB I/O)
# ===========================================================================

async def goal_define(state: VaultAIState) -> VaultAIState:
    """
    Parses goal parameters from request_params and loads V2 analytics.

    Validates:
      - goal_type is one of the supported types (Phase 3 + Phase 4)
      - target_amount > 0
      - horizon_months > 0  OR  target_date is a future date
        (Phase 4 exit criterion: past dates rejected here, before simulation)

    Writes: v2_analytics, v2_expenses, graph_trace, audit_payload
    Raises: ValueError for invalid params, RuntimeError for missing analytics
    """
    trace      = append_trace(state, "goal_define")
    user_id    = state["user_id"]
    req_params = state.get("request_params", {})

    # ── Step 1: validate goal_type ────────────────────────────────────────
    goal_type = str(req_params.get("goal_type", "")).lower().strip()
    if not goal_type:
        raise ValueError("goal_type is required in request_params.")
    if goal_type not in VALID_GOAL_TYPES:
        raise ValueError(
            f"Invalid goal_type '{goal_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_GOAL_TYPES))}"
        )

    # ── Step 2: validate target_amount ───────────────────────────────────
    target_amount = req_params.get("target_amount")
    if not target_amount or float(target_amount) <= 0:
        raise ValueError("target_amount must be a positive number in request_params.")

    # ── Step 3: resolve horizon_months ───────────────────────────────────
    # target_date (Phase 4 travel goal) takes precedence over horizon_months.
    # Past dates are rejected here — Phase 4 exit criterion.
    target_date_str = req_params.get("target_date")
    if target_date_str:
        # Raises ValueError if date is in the past
        horizon_months = _horizon_from_target_date(str(target_date_str))
    else:
        horizon_months = req_params.get("horizon_months")
        if not horizon_months or int(horizon_months) <= 0:
            raise ValueError(
                "horizon_months must be a positive integer in request_params "
                "(or provide a future target_date for travel goals)."
            )
        horizon_months = int(horizon_months)

    # ── Step 4: load V2 analytics ─────────────────────────────────────────
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
            logger.error("goal_define: %s", load_error)

    else:
        load_error = (
            "goal_define requires request_params['_v2_analytics'] "
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
        logger.error("goal_define: DEPENDENCY_UNAVAILABLE — %s", load_error)
        raise RuntimeError(f"goal_define failed: {load_error}")

    existing_payload = state.get("audit_payload") or {}

    logger.info(
        "goal_define: OK — type=%s target=%.0f horizon=%d months",
        goal_type, float(target_amount), horizon_months,
    )

    return {
        **state,
        "v2_analytics":  analytics_result,
        "v2_expenses":   [],
        "graph_trace":   trace,
        "audit_payload": {
            **existing_payload,
            "v2_load_metrics": {"data_days_available": 90},
            "goal_params": {
                "goal_type":      goal_type,
                "target_amount":  float(target_amount),
                "horizon_months": horizon_months,
            },
        },
    }


# ===========================================================================
# NODE 2 — goal_simulate  (sync: pure forecast.py math)
# ===========================================================================

def goal_simulate(state: VaultAIState) -> VaultAIState:
    """
    Runs the appropriate forecast function based on goal_type.

    Phase 3 (preserved):
        savings, emergency_fund, purchase, education, retirement
        → goal_feasibility() + contribution_required()

    Phase 4 (added):
        travel      → same as standard but horizon derived from target_date
        debt_payoff → debt_payoff_schedule()
        multi_goal  → multi_goal_tradeoff()

    Writes: projected_outcomes, assumptions, constraints
    constraints stored verbatim so goal_validate can re-run identically.
    """
    trace      = append_trace(state, "goal_simulate")
    analytics  = get_v2_analytics(state)
    req_params = state.get("request_params", {})

    goal_type       = str(req_params.get("goal_type", "goal")).lower()
    target_amount   = float(req_params["target_amount"])
    current_savings = float(req_params.get("current_savings", 0))
    annual_rate     = float(req_params.get("annual_rate", DEFAULT_ANNUAL_RATE))
    monthly_savings = _derive_monthly_savings(analytics, req_params)

    # Resolve horizon — target_date already validated in goal_define
    target_date_str = req_params.get("target_date")
    if target_date_str:
        horizon_months = _horizon_from_target_date(str(target_date_str))
    else:
        horizon_months = int(req_params.get("horizon_months", 12))

    # ── Route by goal_type ────────────────────────────────────────────────

    if goal_type == "debt_payoff":
        # Phase 4: debt payoff uses amortisation schedule
        outstanding     = float(req_params.get("outstanding", target_amount))
        interest_rate   = float(req_params.get("interest_rate", annual_rate))
        monthly_payment = float(req_params.get("monthly_payment", monthly_savings))

        schedule = debt_payoff_schedule(
            outstanding          = outstanding,
            annual_interest_rate = interest_rate,
            monthly_payment      = monthly_payment,
        )

        projected_outcomes = {
            "goal_type":             goal_type,
            "outstanding":           outstanding,
            "monthly_payment":       monthly_payment,
            "total_months":          schedule["total_months"],
            "total_interest_paid":   schedule["total_interest_paid"],
            "total_paid":            schedule["total_paid"],
            "interest_saved":        schedule["interest_saved"],
            "payment_sufficient":    schedule["payment_sufficient"],
            "feasibility_label":     "FEASIBLE" if schedule["payment_sufficient"] else "INFEASIBLE",
            "projected_balance":     0.0,
            "gap_amount":            0.0,
            "surplus":               0.0,
            "coverage_ratio":        1.0 if schedule["payment_sufficient"] else 0.0,
            "contribution_required": monthly_payment,
            "payoff_schedule":       schedule["payoff_schedule"],
        }
        assumptions = {
            "goal_type":       goal_type,
            "target_amount":   outstanding,
            "horizon_months":  schedule.get("total_months") or horizon_months,
            "current_savings": 0.0,
            "monthly_savings": monthly_payment,
            "annual_rate":     interest_rate,
        }
        constraints = {
            "goal_type":       goal_type,
            "outstanding":     outstanding,
            "interest_rate":   interest_rate,
            "monthly_payment": monthly_payment,
        }

    elif goal_type == "multi_goal":
        # Phase 4: allocate budget across 2-5 concurrent goals
        sub_goals = req_params.get("sub_goals", [])
        if not sub_goals or len(sub_goals) < 2:
            raise ValueError(
                "multi_goal requires 'sub_goals' list with 2-5 goal dicts "
                "in request_params."
            )

        tradeoff = multi_goal_tradeoff(
            goals                   = sub_goals,
            total_monthly_available = monthly_savings,
            annual_rate             = annual_rate,
        )

        feasible_count = sum(
            1 for a in tradeoff["allocations"]
            if a["feasibility"]["label"] == "FEASIBLE"
        )
        total_count = len(tradeoff["allocations"])
        if feasible_count == total_count:
            overall_label = "FEASIBLE"
        elif feasible_count >= total_count // 2:
            overall_label = "STRETCH"
        else:
            overall_label = "INFEASIBLE"

        projected_outcomes = {
            "goal_type":               goal_type,
            "feasibility_label":       overall_label,
            "feasible_goals":          feasible_count,
            "total_goals":             total_count,
            "total_monthly_allocated": tradeoff["total_allocated"],
            "unallocated":             tradeoff["unallocated"],
            "allocations":             tradeoff["allocations"],
            "tradeoff_summary":        tradeoff["tradeoff_summary"],
            "projected_balance":       0.0,
            "gap_amount":              0.0,
            "surplus":                 0.0,
            "coverage_ratio":          round(feasible_count / total_count, 4),
            "contribution_required":   monthly_savings,
            "months_to_goal":          None,
        }
        assumptions = {
            "goal_type":               goal_type,
            "target_amount":           sum(g.get("target_amount", 0) for g in sub_goals),
            "horizon_months":          horizon_months,
            "current_savings":         0.0,
            "monthly_savings":         monthly_savings,
            "annual_rate":             annual_rate,
        }
        constraints = {
            "goal_type":               goal_type,
            "total_monthly_available": monthly_savings,
            "annual_rate":             annual_rate,
            "sub_goals":               sub_goals,
        }

    else:
        # Phase 3 standard path (savings, emergency_fund, purchase,
        # education, retirement) + Phase 4 travel goal (same math,
        # horizon already resolved from target_date above)
        feasibility = goal_feasibility(
            target_amount   = target_amount,
            current_savings = current_savings,
            monthly_savings = monthly_savings,
            annual_rate     = annual_rate,
            horizon_months  = horizon_months,
        )

        required = contribution_required(
            target_amount   = target_amount,
            current_savings = current_savings,
            annual_rate     = annual_rate,
            horizon_months  = horizon_months,
        )

        logger.info(
            "goal_simulate: type=%s target=%.0f horizon=%d "
            "monthly_savings=%.0f label=%s coverage=%.2f",
            goal_type, target_amount, horizon_months,
            monthly_savings, feasibility["label"], feasibility["coverage_ratio"],
        )

        projected_outcomes = {
            "goal_type":             goal_type,
            "feasibility_label":     feasibility["label"],
            "projected_balance":     feasibility["projected_balance"],
            "gap_amount":            feasibility["gap_amount"],
            "surplus":               feasibility["surplus"],
            "months_to_goal":        feasibility["months_to_goal"],
            "coverage_ratio":        feasibility["coverage_ratio"],
            "contribution_required": required["monthly_contribution_required"],
            "total_to_contribute":   required["total_to_contribute"],
            "is_already_feasible":   required["is_already_feasible"],
        }
        # Constraints stored verbatim for goal_validate to re-run identically
        assumptions = {
            "goal_type":       goal_type,
            "target_amount":   target_amount,
            "horizon_months":  horizon_months,
            "current_savings": current_savings,
            "monthly_savings": monthly_savings,
            "annual_rate":     annual_rate,
        }
        constraints = {
            "goal_type":       goal_type,
            "target_amount":   target_amount,
            "current_savings": current_savings,
            "monthly_savings": monthly_savings,
            "annual_rate":     annual_rate,
            "horizon_months":  horizon_months,
        }

    return {
        **state,
        "graph_trace":        trace,
        "projected_outcomes": projected_outcomes,
        "assumptions":        assumptions,
        "constraints":        constraints,
    }


# ===========================================================================
# NODE 3 — goal_validate  (sync: checkpoint)
# ===========================================================================

def goal_validate(state: VaultAIState) -> VaultAIState:
    """
    CHECKPOINT — delegates to run_goal_checkpoint() in checkpoint.py.

    Phase 3 (preserved):
        Re-runs goal_feasibility() and asserts label + balance match.
        A STRETCH or INFEASIBLE result is still PASSED if it matches —
        the checkpoint is about reproducibility, not about being optimistic.

    Phase 4 (added via checkpoint.py):
        debt_payoff → re-runs debt_payoff_schedule(), checks payment_sufficient
        multi_goal  → re-runs multi_goal_tradeoff(), checks feasible_goals count

    PASSED → graph routes to goal_explain
    FAILED → graph routes to goal_fallback
    """
    from app.agents.goal.checkpoint import run_goal_checkpoint

    trace  = append_trace(state, "goal_validate")
    stored = state.get("projected_outcomes")
    cons   = state.get("constraints")

    if stored is None or cons is None:
        reason = "projected_outcomes or constraints missing — goal_simulate did not run"
        logger.error("goal_validate: %s", reason)
        return {
            **state, **mark_degraded(state, reason),
            "graph_trace":       trace,
            "validation_status": ValidationStatus.FAILED,
            "validation_errors": [reason],
        }

    result = run_goal_checkpoint(stored, cons)

    if not result.passed:
        logger.warning("goal_validate: FAILED — %s", result.errors)
        return {
            **state, **mark_degraded(state, result.errors[0]),
            "graph_trace":       trace,
            "validation_status": ValidationStatus.FAILED,
            "validation_errors": result.errors,
        }

    logger.info(
        "goal_validate: PASSED — label=%s",
        stored.get("feasibility_label"),
    )
    return {
        **state,
        "graph_trace":       trace,
        "validation_status": ValidationStatus.PASSED,
        "validation_errors": [],
    }


# ===========================================================================
# NODE 4 — goal_explain  (async: Groq HTTP I/O)
# ===========================================================================

async def goal_explain(state: VaultAIState) -> VaultAIState:
    """
    Calls Groq LLM to narrate the goal feasibility result in plain English.

    Prompt includes: goal type, target, horizon, current savings,
    monthly savings, label, gap/surplus, contribution required.
    Does NOT include raw market data or predicted returns.

    INFEASIBLE goals get a constructive prompt focused on timeline extension
    rather than rejection.
    """
    trace       = append_trace(state, "goal_explain")
    outcomes    = state.get("projected_outcomes") or {}
    assumptions = state.get("assumptions") or {}

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("goal_explain: GROQ_API_KEY not set — skipping LLM")
        return {
            **state, **mark_degraded(state, "GROQ_API_KEY not configured"),
            "graph_trace": trace, "llm_explanation": None,
        }

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
        f"Goal feasibility result:\n"
        f"Goal type: {goal_type}\n"
        f"Target amount: Rs.{target:,.0f}\n"
        f"Horizon: {horizon} months\n"
        f"Current savings: Rs.{current:,.0f}\n"
        f"Monthly savings: Rs.{monthly:,.0f}/month\n"
        f"Result: {label}\n"
        f"Projected balance at end: Rs.{outcomes.get('projected_balance', 0):,.0f}\n"
        f"Gap (if any): Rs.{gap:,.0f}\n"
        f"Surplus (if any): Rs.{surplus:,.0f}\n"
        f"Months to reach goal: {months_to_str}\n"
        f"Monthly contribution required to reach goal: Rs.{contrib:,.0f}\n"
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
        logger.info("goal_explain: LLM OK (%d chars)", len(raw))
        return {**state, "graph_trace": trace, "llm_explanation": raw}

    except httpx.TimeoutException:
        msg = f"Groq timed out after {GROQ_TIMEOUT_S}s"
        logger.warning("goal_explain: %s", msg)
    except httpx.HTTPStatusError as exc:
        # Log full Groq error body so we know exactly what went wrong
        try:
            error_body = exc.response.text
        except Exception:
            error_body = "(could not read response body)"
        msg = f"Groq HTTP {exc.response.status_code}: {error_body}"
        logger.error("goal_explain: %s", msg)
    except Exception as exc:
        msg = f"Groq call failed: {type(exc).__name__}: {exc}"
        logger.error("goal_explain: %s", msg)

    return {
        **state, **mark_degraded(state, msg),
        "graph_trace": trace, "llm_explanation": None,
    }


# ===========================================================================
# NODE 5 — goal_filter  (sync: string scrubbing)
# ===========================================================================

def goal_filter(state: VaultAIState) -> VaultAIState:
    """
    Scrubs llm_explanation and writes explanation_filtered.
    If llm_explanation is None → deterministic summary.

    Delegates to llm_output_filter.filter_llm_output() which runs:
      1. Speculative language removal
      2. Directive language removal
      3. Numeric guard (redacts hallucinated numbers)
      4. Cleanup
    """
    trace    = append_trace(state, "goal_filter")
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

    return {**state, "graph_trace": trace, "explanation_filtered": filtered}


# ===========================================================================
# NODE 6 — goal_fallback  (sync: template build)
# ===========================================================================

def goal_fallback(state: VaultAIState) -> VaultAIState:
    """
    Reached when goal_validate returns FAILED.
    Builds deterministic summary, marks degraded, skips LLM.
    """
    trace    = append_trace(state, "goal_fallback")
    outcomes = state.get("projected_outcomes") or {}
    assum    = state.get("assumptions") or {}
    errors   = state.get("validation_errors") or ["validation failed"]
    reason   = errors[0]

    summary = (
        _build_deterministic_summary(outcomes, assum)
        if outcomes
        else (
            "Unable to generate a goal plan: simulation results could not be "
            "validated. Please try again or contact support."
        )
    )

    logger.warning("goal_fallback: degraded — %s", reason)
    return {
        **state, **mark_degraded(state, reason),
        "graph_trace":          trace,
        "explanation_filtered": summary,
    }