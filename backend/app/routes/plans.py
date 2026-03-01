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


class AllocationItem(BaseModel):
    category:      str
    requested:     float
    allocated:     float
    cut_amount:    float
    cut_pct:       float
    priority:      str


class BudgetAllocation(BaseModel):
    status:              str    # FEASIBLE | INFEASIBLE | DEFICIT
    income_monthly:      float
    savings_target:      float
    total_fixed:         float
    discretionary_pool:  float
    allocations:         list[AllocationItem]
    total_allocated:     float
    actual_savings:      float
    savings_gap:         float
    surplus:             float


class ProjectedOutcomes(BaseModel):
    monthly_savings:    float
    annual_savings:     float
    savings_rate:       float
    budget_allocation:  dict    # full allocate_budget() output
    optimizer_used:     str


class ConfidenceBlock(BaseModel):
    overall:         float
    data_coverage:   float
    assumption_risk: str


class BudgetPlanResponse(BaseModel):
    plan_id:              Optional[str]
    plan_type:            str
    projected_outcomes:   Optional[dict]
    explanation:          Optional[str]
    confidence:           Optional[dict]
    degraded:             bool
    graph_trace:          list[str]
    source_hash:          Optional[str]


# ---------------------------------------------------------------------------
# POST /plans/budget
# ---------------------------------------------------------------------------

@router.post(
    "/budget",
    response_model=BudgetPlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a budget plan",
    description=(
        "Runs the full budget agent pipeline: V2 analytics → optimizer → "
        "validation checkpoint → LLM explanation → DB persist."
    ),
)
async def create_budget_plan(
    body:         BudgetPlanRequest,
    current_user: Any = Depends(get_current_user),
    db:           Any = Depends(get_db),
) -> BudgetPlanResponse:
    """
    POST /plans/budget

    Full flow:
      1. Pre-fetch V2 analytics (async DB call in route's async context)
      2. Build graph state
      3. await graph.ainvoke()
      4. Return structured response
    """
    user_id = str(current_user.id)

    # ── Step 1: Pre-fetch V2 analytics ────────────────────────────────────
    # Done here because we have the AsyncSession from DI and are already async.
    # The budget_load_v2 node picks this up from request_params["_v2_analytics"].
    try:
        v2_analytics = await build_trends_report(db, current_user.id)
    except Exception as exc:
        logger.error("create_budget_plan: build_trends_report failed for user %s: %s",
                     user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Spending history could not be loaded. "
                "Ensure expenses have been recorded before generating a budget plan."
            ),
        )

    # ── Step 2: Build initial state ───────────────────────────────────────
    initial_state = make_initial_state(
        user_id        = user_id,
        user_message   = body.message,
        request_params = {
            "_plan_type":         PlanType.BUDGET.value,   # bypass intent_classifier
            "_v2_analytics":      v2_analytics,            # pre-fetched above
            "_db":                db,
            "income_monthly":     body.income_monthly,
            "savings_target_pct": body.savings_target_pct,
            "fixed_categories":   body.fixed_categories,
        },
    )

    # ── Step 3: Run graph ─────────────────────────────────────────────────
    try:
        result = await _graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": user_id}},
        )
    except ValueError as exc:
        # income_monthly missing or zero — user error
        logger.warning("create_budget_plan: validation error for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except RuntimeError as exc:
        # budget_load_v2 dependency failure (shouldn't happen — we pre-fetched above)
        logger.error("create_budget_plan: runtime error for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Budget plan generation failed. Please try again.",
        )
    except Exception as exc:
        logger.error("create_budget_plan: unexpected error for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    # ── Step 4: Build response ────────────────────────────────────────────
    return BudgetPlanResponse(
        plan_id             = result.get("plan_id"),
        plan_type           = str(result.get("plan_type", PlanType.BUDGET)),
        projected_outcomes  = result.get("projected_outcomes"),
        explanation         = result.get("explanation_filtered"),
        confidence          = result.get("confidence"),
        degraded            = result.get("degraded", False),
        graph_trace         = result.get("graph_trace", []),
        source_hash         = result.get("source_hash"),
    )


# ---------------------------------------------------------------------------
# STUB endpoints — Phase 4/5/6
# ---------------------------------------------------------------------------

@router.post("/invest", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_invest_plan() -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Investment plans are coming in Phase 4.",
    )


@router.post("/goal", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_goal_plan() -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Goal plans are coming in Phase 5.",
    )


@router.post("/chat", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_chat_plan() -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Chat-based planning is coming in Phase 6.",
    )


@router.get("/{plan_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_plan(plan_id: str) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Plan retrieval is coming in Phase 4.",
    )


@router.get("/{plan_id}/trace", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_plan_trace(plan_id: str) -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Trace retrieval is coming in Phase 4.",
    )