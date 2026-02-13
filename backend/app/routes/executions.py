from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.execution import InsightExecution
from app.middleware.auth import get_current_user
from app.models.user import User

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

    # ✅ PENDING or LOCKED
    if execution.status in ("pending", "locked"):
        return {
            "status": execution.status,
            "execution_id": execution.id,
        }

    # ✅ RUNNING
    if execution.status == "running":
        return {
            "status": "running"
        }

    # ✅ SUCCESS
    if execution.status == "success":
        return {
            "status": "ready",
            "execution_id": execution.id,
            "cached": True,
            "rag_context": execution.rag_snapshot,
            "data": {
                "metrics": execution.analytics_snapshot,
                "explanation": execution.llm_output,
            }
        }

    # ✅ FALLBACK
    if execution.status == "fallback":
        return {
            "status": "ready",
            "execution_id": execution.id,
            "cached": True,
            "fallback": True,
            "data": {
                "metrics": execution.analytics_snapshot,
                "explanation": execution.llm_output,
            }
        }

    # ✅ FAILED or CANCELLED
    return {
        "status": "failed",
        "execution_id": execution.id,
        "error": execution.error_message or "Unknown error",
        "step_failed": execution.step_failed,
    }