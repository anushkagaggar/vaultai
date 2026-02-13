from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.execution import InsightExecution
from app.middleware.auth import get_current_user
from app.models.user import User
from app.orchestrator.state import State  

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("/{execution_id}")
async def get_execution(
    execution_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InsightExecution).where(
            InsightExecution.id == execution_id,
            InsightExecution.user_id == user.id,
        )
    )

    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # ✅ Compute terminal flag
    is_terminal = State.is_terminal(execution.status)

    # =====================================
    # NON-TERMINAL STATES
    # =====================================
    
    # PENDING or LOCKED
    if execution.status in (State.PENDING, State.LOCKED):
        return {
            "execution_id": execution.id,
            "status": execution.status,
            "is_terminal": False,  # ✅ Explicit contract
        }

    # RUNNING
    if execution.status == State.RUNNING:
        return {
            "execution_id": execution.id,
            "status": "running",
            "is_terminal": False,  # ✅ Explicit contract
        }

    # =====================================
    # TERMINAL STATES
    # =====================================
    
    # SUCCESS
    if execution.status == State.SUCCESS:
        return {
            "execution_id": execution.id,
            "status": "success",
            "is_terminal": True,  # ✅ Polling can stop
            "result": {
                "metrics": execution.analytics_snapshot,
                "explanation": execution.llm_output,
            }
        }

    # FALLBACK (terminal but degraded)
    if execution.status == State.FALLBACK:
        return {
            "execution_id": execution.id,
            "status": "fallback",
            "is_terminal": True,  # ✅ Polling can stop
            "result": {
                "metrics": execution.analytics_snapshot,
                "explanation": execution.llm_output,
            }
        }

    # FAILED or CANCELLED (terminal with error)
    return {
        "execution_id": execution.id,
        "status": execution.status,  # "failed" or "cancelled"
        "is_terminal": True,  # ✅ Polling can stop
        "error": execution.error_message or "Unknown error",
        "error_code": execution.error_code,
    }