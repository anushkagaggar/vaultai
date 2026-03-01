"""
VaultAI V3 — routes/plans.py
=============================
FastAPI route handlers for plan generation endpoints.

POST /plans/budget  — budget plan (LIVE — wired to real graph nodes)
POST /plans/invest  — investment plan (STUB — Phase 4)
POST /plans/goal    — goal plan (STUB — Phase 5)
POST /plans/chat    — natural language routing (STUB — Phase 6)
GET  /plans/{id}    — retrieve a stored plan (STUB)
GET  /plans/{id}/trace — execution trace (STUB)

FLOW FOR POST /plans/budget
----------------------------
1. Authenticate user (JWT → current_user)
2. Pre-fetch V2 analytics (await build_trends_report) — async context
3. Build initial state (make_initial_state)
4. await graph.ainvoke(state)   ← NOT graph.invoke()
5. Return PlanResponse

WHY PRE-FETCH IN THE ROUTE
---------------------------
build_trends_report() needs an AsyncSession from the FastAPI dependency
injection system. The graph nodes don't have access to the DI system —
they receive state dicts. Pre-fetching in the route is the clean bridge:
the route is already async, already has the DB session, and can inject the
result as request_params["_v2_analytics"]. The budget_load_v2 node picks
it up from there with zero extra DB calls.

This mirrors the exact pattern in runner.py's InsightRunner.run() Step 1.

Author: VaultAI V3
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.agents.State import make_initial_state, PlanType
from app.agents.graph import compile_graph
from app.analytics.trends import build_trends_report
from app.middleware.auth import get_current_user   # your existing JWT dep
from app.database import get_db                       # your existing DB dep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plans", tags=["plans"])

# Compile once at module load — if the graph is misconfigured this fails fast
_graph = compile_graph()


# ---------------------------------------------------------------------------
# Shared response model
# ---------------------------------------------------------------------------
class PlanResponse(BaseModel):
    plan_id:             Optional[int]
    plan_type:           str
    projected_outcomes:  Optional[dict]
    explanation:         Optional[str]
    confidence:          Optional[dict]
    degraded:            bool
    graph_trace:         list[str]
    source_hash:         Optional[str]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class BudgetPlanRequest(BaseModel):
    """
    Request body for POST /plans/budget.

    income_monthly is required — V2 has no income model so it cannot be
    inferred from spending history.
    """
    income_monthly:      float = Field(..., gt=0, description="Monthly take-home income")
    savings_target_pct:  float = Field(0.20,  ge=0, le=1,
                                        description="Target savings as fraction of income (0–1)")
    fixed_categories:    list[str] = Field(default_factory=list,
                                           description="Category names that cannot be cut")
    message:             str  = Field("help me budget",
                                      description="Natural language context (optional)")

    @field_validator("income_monthly")
    @classmethod
    def income_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("income_monthly must be greater than 0")
        return v


class InvestPlanRequest(BaseModel):
    investment_amount: float = Field(..., gt=0,
                                     description="Lump sum amount to invest")
    risk_profile:      str   = Field("moderate",
                                     description="conservative | moderate | aggressive")
    horizon_months:    int   = Field(36, gt=0,
                                     description="Investment horizon in months")
    income_monthly:    float = Field(0.0, ge=0,
                                     description="Monthly income (optional, for surplus calc)")
    message:           str   = Field("help me invest")

    @field_validator("risk_profile")
    @classmethod
    def valid_profile(cls, v: str) -> str:
        allowed = {"conservative", "moderate", "aggressive"}
        if v.lower() not in allowed:
            raise ValueError(f"risk_profile must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


class GoalPlanRequest(BaseModel):
    goal_type:       str   = Field(...,
                                   description="savings | emergency_fund | purchase | education | retirement")
    target_amount:   float = Field(..., gt=0,
                                   description="Monetary goal to reach")
    horizon_months:  int   = Field(..., gt=0,
                                   description="Months until target date")
    current_savings: float = Field(0.0, ge=0,
                                   description="Starting balance")
    monthly_savings: Optional[float] = Field(None, ge=0,
                                             description="Fixed monthly contribution (derived from V2 if omitted)")
    annual_rate:     float = Field(0.07, ge=0, le=1,
                                   description="Expected annual growth rate (decimal)")
    income_monthly:  float = Field(0.0, ge=0,
                                   description="Monthly income (used to derive monthly_savings if omitted)")
    message:         str   = Field("help me with my goal")

    @field_validator("goal_type")
    @classmethod
    def valid_goal_type(cls, v: str) -> str:
        allowed = {"savings", "emergency_fund", "purchase", "education", "retirement"}
        if v.lower() not in allowed:
            raise ValueError(f"goal_type must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


# ---------------------------------------------------------------------------
# Shared graph runner — keeps route handlers DRY
# ---------------------------------------------------------------------------

async def _run_graph(
    plan_type:     PlanType,
    user_id:       str,
    user_message:  str,
    request_params: dict,
    db:            Any,
) -> dict:
    """
    Build state, call ainvoke, handle common exceptions.
    Returns the raw result dict from the graph.
    """
    initial_state = make_initial_state(
        user_id        = user_id,
        user_message   = user_message,
        request_params = {
            "_plan_type":    plan_type.value,
            **request_params,
        },
    )

    try:
        result = await _graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": user_id, "db": db}},
        )
    except ValueError as exc:
        logger.warning("graph ValueError for user %s: %s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc))
    except RuntimeError as exc:
        logger.error("graph RuntimeError for user %s: %s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Plan generation failed. Please try again.")
    except Exception as exc:
        logger.error("graph unexpected error for user %s: %s", user_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="An unexpected error occurred.")

    return result


def _to_response(result: dict, plan_type: PlanType) -> PlanResponse:
    pt = result.get("plan_type", plan_type)
    pt_str = pt.value if hasattr(pt, "value") else str(pt)
    return PlanResponse(
        plan_id            = result.get("plan_id"),
        plan_type          = pt_str,
        projected_outcomes = result.get("projected_outcomes"),
        explanation        = result.get("explanation_filtered"),
        confidence         = result.get("confidence"),
        degraded           = result.get("degraded", False),
        graph_trace        = result.get("graph_trace", []),
        source_hash        = result.get("source_hash"),
    )


# ---------------------------------------------------------------------------
# POST /plans/budget
# ---------------------------------------------------------------------------

@router.post("/budget", response_model=PlanResponse,
             status_code=status.HTTP_201_CREATED)
async def create_budget_plan(
    body:         BudgetPlanRequest,
    current_user: Any = Depends(get_current_user),
    db:           Any = Depends(get_db),
) -> PlanResponse:
    user_id = str(current_user.id)

    try:
        v2_analytics = await build_trends_report(db, current_user.id)
    except Exception as exc:
        logger.error("build_trends_report failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spending history could not be loaded. Record expenses first.",
        )

    result = await _run_graph(
        plan_type     = PlanType.BUDGET,
        user_id       = user_id,
        user_message  = body.message,
        request_params = {
            "_v2_analytics":      v2_analytics,
            "income_monthly":     body.income_monthly,
            "savings_target_pct": body.savings_target_pct,
            "fixed_categories":   body.fixed_categories,
        },
        db = db,
    )
    return _to_response(result, PlanType.BUDGET)


# ---------------------------------------------------------------------------
# POST /plans/invest
# ---------------------------------------------------------------------------

@router.post("/invest", response_model=PlanResponse,
             status_code=status.HTTP_201_CREATED)
async def create_invest_plan(
    body:         InvestPlanRequest,
    current_user: Any = Depends(get_current_user),
    db:           Any = Depends(get_db),
) -> PlanResponse:
    user_id = str(current_user.id)

    try:
        v2_analytics = await build_trends_report(db, current_user.id)
    except Exception as exc:
        logger.error("build_trends_report failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spending history could not be loaded. Record expenses first.",
        )

    result = await _run_graph(
        plan_type     = PlanType.INVEST,
        user_id       = user_id,
        user_message  = body.message,
        request_params = {
            "_v2_analytics":   v2_analytics,
            "investment_amount": body.investment_amount,
            "risk_profile":    body.risk_profile,
            "horizon_months":  body.horizon_months,
            "income_monthly":  body.income_monthly,
        },
        db = db,
    )
    return _to_response(result, PlanType.INVEST)


# ---------------------------------------------------------------------------
# POST /plans/goal
# ---------------------------------------------------------------------------

@router.post("/goal", response_model=PlanResponse,
             status_code=status.HTTP_201_CREATED)
async def create_goal_plan(
    body:         GoalPlanRequest,
    current_user: Any = Depends(get_current_user),
    db:           Any = Depends(get_db),
) -> PlanResponse:
    user_id = str(current_user.id)

    try:
        v2_analytics = await build_trends_report(db, current_user.id)
    except Exception as exc:
        logger.error("build_trends_report failed for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spending history could not be loaded. Record expenses first.",
        )

    params: dict = {
        "_v2_analytics":   v2_analytics,
        "goal_type":       body.goal_type,
        "target_amount":   body.target_amount,
        "horizon_months":  body.horizon_months,
        "current_savings": body.current_savings,
        "annual_rate":     body.annual_rate,
        "income_monthly":  body.income_monthly,
    }
    # Only inject monthly_savings if explicitly provided — otherwise goal_simulate derives it
    if body.monthly_savings is not None:
        params["monthly_savings"] = body.monthly_savings

    result = await _run_graph(
        plan_type     = PlanType.GOAL,
        user_id       = user_id,
        user_message  = body.message,
        request_params = params,
        db = db,
    )
    return _to_response(result, PlanType.GOAL)


# ---------------------------------------------------------------------------
# STUB endpoints — Phase 5+
# ---------------------------------------------------------------------------

@router.post("/chat", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_chat_plan() -> dict:
    raise HTTPException(status_code=501, detail="Chat planning coming in Phase 6.")


@router.get("/{plan_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_plan(plan_id: int) -> dict:
    raise HTTPException(status_code=501, detail="Plan retrieval coming in Phase 5.")


@router.get("/{plan_id}/trace", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_plan_trace(plan_id: int) -> dict:
    raise HTTPException(status_code=501, detail="Trace retrieval coming in Phase 5.")