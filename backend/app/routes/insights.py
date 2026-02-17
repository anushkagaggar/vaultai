from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.orchestrator import InsightRunner
from app.orchestrator.state import State
from app.insights.resolver import resolve_insight  # ✅ NEW

router = APIRouter(prefix="/insights", tags=["Insights"])
runner = InsightRunner()


# =====================================================
# GET — Read path (artifact resolver)
# =====================================================

@router.get("/trends")
async def get_trends_insight(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Get the latest trusted insight artifact.
    
    This endpoint:
    - NEVER triggers computation
    - Returns cached artifact if fresh
    - Returns stale status if data changed
    - Returns unavailable if never computed
    
    Use POST to start computation.
    """
    
    result = await resolve_insight(
        db=db,
        user_id=user.id,
        insight_type="trends"
    )
    
    return result


# =====================================================
# POST — Write path (start execution)
# =====================================================

@router.post("/trends")
async def start_trends_computation(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Start insight computation.
    
    This endpoint:
    - ALWAYS starts new execution (or reuses active one)
    - NEVER returns insight data directly
    - Returns execution_id for polling
    
    Use GET /executions/{id} to poll for results.
    Use GET /insights/trends to read cached insight.
    """
    
    execution, result = await runner.run(db, user.id, "trends")

    # ✅ NEW: POST never returns insight data
    # Only returns execution tracking info
    
    if State.is_terminal(execution.status):
        
        if execution.status == State.SUCCESS:
            return {
                "status": "completed",
                "execution_id": execution.id,
                "message": "Insight computed successfully. Use GET /insights/trends to retrieve."
            }
        
        elif execution.status == State.FALLBACK:
            return {
                "status": "completed",
                "execution_id": execution.id,
                "degraded": True,
                "message": "Computation completed with degraded quality. Use GET /insights/trends to retrieve."
            }
        
        elif execution.status == State.FAILED:
            return {
                "status": "failed",
                "execution_id": execution.id,
                "error": execution.error_message,
            }
    
    # Non-terminal (running/pending)
    return {
        "status": "started",
        "execution_id": execution.id,
        "message": "Computation started. Poll GET /executions/{id} for progress."
    }