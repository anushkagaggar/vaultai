"""
VaultAI V3 — routes/plans.py
=============================
FastAPI route handlers for plan generation and retrieval.

LIVE:
    POST /plans/budget          — budget agent
    POST /plans/invest          — invest agent
    POST /plans/goal            — goal agent
    POST /plans/chat            — natural language routing
    GET  /plans/{plan_id}       — fetch stored plan by id
    GET  /plans/{plan_id}/trace — fetch just the graph_trace

CHAT ENDPOINT DESIGN
--------------------
POST /plans/chat accepts a plain-language message plus a loose params dict.
It runs intent_classifier (the same rule-based node used by the graph)
to determine plan_type, then dispatches to the same graph with the same
_v2_analytics pre-fetch pattern used by the direct endpoints.

The user still needs to provide numeric params (income_monthly,
investment_amount, etc.) because the classifier cannot infer numbers
from prose. If required params are missing for the detected plan_type,
the endpoint returns 422 with a clear message listing what's needed.

Author: VaultAI V3
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.State import make_initial_state, PlanType
from app.agents.graph import compile_graph
from app.agents.router_node import classify_intent
from app.analytics.trends import build_trends_report
from app.middleware.auth import get_current_user
from app.database import get_db
from app.models.plan import Plan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plans", tags=["plans"])

_graph = compile_graph()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class PlanResponse(BaseModel):
    plan_id:            Optional[int]
    plan_type:          str
    projected_outcomes: Optional[dict]
    explanation:        Optional[str]
    confidence:         Optional[dict]
    degraded:           bool
    graph_trace:        list[str]
    source_hash:        Optional[str]


class PlanDetailResponse(PlanResponse):
    """Extended response for GET /plans/{id} — includes DB metadata."""
    status:      str
    assumptions: Optional[dict]
    created_at:  Optional[str]


class TraceResponse(BaseModel):
    plan_id:     int
    plan_type:   str
    graph_trace: list[str]
    degraded:    bool
    status:      str
    created_at:  Optional[str]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class BudgetPlanRequest(BaseModel):
    income_monthly:     float = Field(..., gt=0)
    savings_target_pct: float = Field(0.20, ge=0, le=1)
    fixed_categories:   list[str] = Field(default_factory=list)
    message:            str = Field("help me budget")

    @field_validator("income_monthly")
    @classmethod
    def income_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("income_monthly must be > 0")
        return v


class InvestPlanRequest(BaseModel):
    investment_amount: float = Field(..., gt=0)
    risk_profile:      str   = Field("moderate")
    horizon_months:    int   = Field(36, gt=0)
    income_monthly:    float = Field(0.0, ge=0)
    message:           str   = Field("help me invest")

    @field_validator("risk_profile")
    @classmethod
    def valid_profile(cls, v: str) -> str:
        allowed = {"conservative", "moderate", "aggressive"}
        if v.lower() not in allowed:
            raise ValueError(f"risk_profile must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


class GoalPlanRequest(BaseModel):
    goal_type:       str            = Field(...)
    target_amount:   float          = Field(..., gt=0)
    horizon_months:  int            = Field(..., gt=0)
    current_savings: float          = Field(0.0, ge=0)
    monthly_savings: Optional[float]= Field(None, ge=0)
    annual_rate:     float          = Field(0.07, ge=0, le=1)
    income_monthly:  float          = Field(0.0, ge=0)
    message:         str            = Field("help me with my goal")

    @field_validator("goal_type")
    @classmethod
    def valid_goal_type(cls, v: str) -> str:
        allowed = {"savings", "emergency_fund", "purchase", "education", "retirement"}
        if v.lower() not in allowed:
            raise ValueError(f"goal_type must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


class ChatPlanRequest(BaseModel):
    """
    Natural language plan request.

    The message field drives intent classification.
    All other fields are optional — only the ones required for the detected
    plan_type must be present. If they're missing, the endpoint returns 422
    with a clear error listing exactly what's needed.

    Examples:
        {"message": "help me budget", "income_monthly": 80000}
        {"message": "where should I invest 50000", "investment_amount": 50000}
        {"message": "can I afford a car in 2 years",
         "goal_type": "purchase", "target_amount": 400000, "horizon_months": 24}
    """
    message:           str            = Field(..., min_length=3)

    # Budget params
    income_monthly:    Optional[float]= Field(None, gt=0)
    savings_target_pct:float          = Field(0.20, ge=0, le=1)
    fixed_categories:  list[str]      = Field(default_factory=list)

    # Invest params
    investment_amount: Optional[float]= Field(None, gt=0)
    risk_profile:      str            = Field("moderate")
    horizon_months:    Optional[int]  = Field(None, gt=0)

    # Goal params
    goal_type:         Optional[str]  = Field(None)
    target_amount:     Optional[float]= Field(None, gt=0)
    current_savings:   float          = Field(0.0, ge=0)
    monthly_savings:   Optional[float]= Field(None, ge=0)
    annual_rate:       float          = Field(0.07, ge=0, le=1)


# ---------------------------------------------------------------------------
# Shared graph runner
# ---------------------------------------------------------------------------

async def _run_graph(
    plan_type:      PlanType,
    user_id:        str,
    user_message:   str,
    request_params: dict,
    db:             Any,
) -> dict:
    initial_state = make_initial_state(
        user_id        = user_id,
        user_message   = user_message,
        request_params = {"_plan_type": plan_type.value, **request_params},
    )
    try:
        return await _graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": user_id, "db": db}},
        )
    except ValueError as exc:
        logger.warning("graph ValueError user=%s: %s", user_id, exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        logger.error("graph RuntimeError user=%s: %s", user_id, exc)
        raise HTTPException(status_code=503, detail="Plan generation failed. Please try again.")
    except Exception as exc:
        logger.error("graph unexpected error user=%s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")


def _to_response(result: dict, plan_type: PlanType) -> PlanResponse:
    pt = result.get("plan_type", plan_type)
    return PlanResponse(
        plan_id            = result.get("plan_id"),
        plan_type          = pt.value if hasattr(pt, "value") else str(pt),
        projected_outcomes = result.get("projected_outcomes"),
        explanation        = result.get("explanation_filtered"),
        confidence         = result.get("confidence"),
        degraded           = result.get("degraded", False),
        graph_trace        = result.get("graph_trace", []),
        source_hash        = result.get("source_hash"),
    )


async def _prefetch_analytics(db: Any, user_id_int: int, user_id_str: str) -> dict:
    """Pre-fetch V2 analytics — shared by all POST endpoints."""
    try:
        return await build_trends_report(db, user_id_int)
    except Exception as exc:
        logger.error("build_trends_report failed user=%s: %s", user_id_str, exc)
        raise HTTPException(
            status_code=503,
            detail="Spending history could not be loaded. Record expenses first.",
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
    v2      = await _prefetch_analytics(db, current_user.id, user_id)
    result  = await _run_graph(
        plan_type      = PlanType.BUDGET,
        user_id        = user_id,
        user_message   = body.message,
        request_params = {
            "_v2_analytics":      v2,
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
    v2      = await _prefetch_analytics(db, current_user.id, user_id)
    result  = await _run_graph(
        plan_type      = PlanType.INVEST,
        user_id        = user_id,
        user_message   = body.message,
        request_params = {
            "_v2_analytics":   v2,
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
    v2      = await _prefetch_analytics(db, current_user.id, user_id)

    params: dict = {
        "_v2_analytics":   v2,
        "goal_type":       body.goal_type,
        "target_amount":   body.target_amount,
        "horizon_months":  body.horizon_months,
        "current_savings": body.current_savings,
        "annual_rate":     body.annual_rate,
        "income_monthly":  body.income_monthly,
    }
    if body.monthly_savings is not None:
        params["monthly_savings"] = body.monthly_savings

    result = await _run_graph(
        plan_type      = PlanType.GOAL,
        user_id        = user_id,
        user_message   = body.message,
        request_params = params,
        db             = db,
    )
    return _to_response(result, PlanType.GOAL)


# ---------------------------------------------------------------------------
# POST /plans/chat
# ---------------------------------------------------------------------------

# Required params per plan_type — used to produce clear 422 messages
_REQUIRED_PARAMS: dict[PlanType, list[str]] = {
    PlanType.BUDGET:  ["income_monthly"],
    PlanType.INVEST:  ["investment_amount"],
    PlanType.GOAL:    ["goal_type", "target_amount", "horizon_months"],
    PlanType.SIMULATE: [],   # stub
    PlanType.COMBINED: [],   # stub
}


@router.post("/chat", response_model=PlanResponse,
             status_code=status.HTTP_201_CREATED)
async def create_chat_plan(
    body:         ChatPlanRequest,
    current_user: Any = Depends(get_current_user),
    db:           Any = Depends(get_db),
) -> PlanResponse:
    """
    Natural language plan entry point.

    1. Classify intent from body.message using the same rule-based classifier
       the graph uses internally — guarantees consistent routing.
    2. Validate that the required numeric params for the detected plan_type
       are present. Return 422 with a specific error if they're missing.
    3. Pre-fetch V2 analytics.
    4. Dispatch to the same graph as the direct endpoints.
    """
    user_id = str(current_user.id)

    # ── Step 1: classify ─────────────────────────────────────────────────
    classification = classify_intent(
        user_message   = body.message,
        request_params = {},   # no _plan_type override — let message drive it
    )
    plan_type = classification.plan_type

    logger.info(
        "chat: user=%s message='%.60s' → %s (keyword='%s')",
        user_id, body.message, plan_type.value,
        classification.matched_keyword or "none",
    )

    # ── Step 2: handle unroutable intents ────────────────────────────────
    if plan_type == PlanType.UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Could not determine what type of plan you need from your message. "
                "Try being more specific: 'Help me budget with Rs.80,000 income', "
                "'Where should I invest Rs.50,000?', or "
                "'Can I save Rs.2,00,000 in 12 months?'"
            ),
        )

    if plan_type in (PlanType.SIMULATE, PlanType.COMBINED):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"{plan_type.value.title()} plans are coming in Phase 5.",
        )

    # ── Step 3: validate required params ─────────────────────────────────
    required = _REQUIRED_PARAMS.get(plan_type, [])
    body_dict = body.model_dump()
    missing = [p for p in required if not body_dict.get(p)]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Your message was classified as a {plan_type.value} plan. "
                f"Please also provide: {', '.join(missing)}."
            ),
        )

    # ── Step 4: pre-fetch analytics ───────────────────────────────────────
    v2 = await _prefetch_analytics(db, current_user.id, user_id)

    # ── Step 5: build params for the detected plan_type ───────────────────
    if plan_type == PlanType.BUDGET:
        params: dict = {
            "_v2_analytics":      v2,
            "income_monthly":     body.income_monthly,
            "savings_target_pct": body.savings_target_pct,
            "fixed_categories":   body.fixed_categories,
        }
    elif plan_type == PlanType.INVEST:
        params = {
            "_v2_analytics":   v2,
            "investment_amount": body.investment_amount,
            "risk_profile":    body.risk_profile,
            "horizon_months":  body.horizon_months or 36,
            "income_monthly":  body.income_monthly or 0.0,
        }
    else:  # GOAL
        params = {
            "_v2_analytics":   v2,
            "goal_type":       body.goal_type,
            "target_amount":   body.target_amount,
            "horizon_months":  body.horizon_months,
            "current_savings": body.current_savings,
            "annual_rate":     body.annual_rate,
            "income_monthly":  body.income_monthly or 0.0,
        }
        if body.monthly_savings is not None:
            params["monthly_savings"] = body.monthly_savings

    # ── Step 6: run graph ─────────────────────────────────────────────────
    result = await _run_graph(
        plan_type      = plan_type,
        user_id        = user_id,
        user_message   = body.message,
        request_params = params,
        db             = db,
    )
    return _to_response(result, plan_type)


# ---------------------------------------------------------------------------
# GET /plans/{plan_id}
# ---------------------------------------------------------------------------

@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(
    plan_id:      int,
    current_user: Any = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
) -> PlanDetailResponse:
    """
    Fetch a stored plan by id.

    Returns 404 if the plan doesn't exist.
    Returns 403 if the plan belongs to a different user.
    """
    stmt   = select(Plan).where(Plan.id == plan_id)
    result = await db.execute(stmt)
    plan   = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")

    if plan.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    return PlanDetailResponse(
        plan_id            = plan.id,
        plan_type          = plan.plan_type,
        projected_outcomes = plan.projected_outcomes,
        explanation        = plan.explanation,
        confidence         = plan.confidence,
        degraded           = plan.degraded,
        graph_trace        = plan.graph_trace or [],
        source_hash        = plan.source_hash,
        status             = plan.status,
        assumptions        = plan.assumptions,
        created_at         = plan.created_at.isoformat() if plan.created_at else None,
    )


# ---------------------------------------------------------------------------
# GET /plans/{plan_id}/trace
# ---------------------------------------------------------------------------

@router.get("/{plan_id}/trace", response_model=TraceResponse)
async def get_plan_trace(
    plan_id:      int,
    current_user: Any = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
) -> TraceResponse:
    """
    Fetch just the execution trace for a plan.

    Lightweight — returns only diagnostic fields, not the full plan content.
    Returns 404 if the plan doesn't exist.
    Returns 403 if the plan belongs to a different user.
    """
    stmt   = select(Plan).where(Plan.id == plan_id)
    result = await db.execute(stmt)
    plan   = result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found.")

    if plan.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    return TraceResponse(
        plan_id     = plan.id,
        plan_type   = plan.plan_type,
        graph_trace = plan.graph_trace or [],
        degraded    = plan.degraded,
        status      = plan.status,
        created_at  = plan.created_at.isoformat() if plan.created_at else None,
    )