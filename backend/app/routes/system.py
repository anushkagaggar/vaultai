from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.execution import InsightExecution
from app.models.insight import Insight
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/metrics")
async def get_system_metrics(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    System observability metrics for the execution monitor.
    Returns counts and rates for the current user.
    """

    # Total executions
    total_stmt = select(func.count(InsightExecution.id)).where(
        InsightExecution.user_id == user.id
    )
    total = (await db.execute(total_stmt)).scalar() or 0

    # Success count
    success_stmt = select(func.count(InsightExecution.id)).where(
        InsightExecution.user_id == user.id,
        InsightExecution.status == "success"
    )
    success_count = (await db.execute(success_stmt)).scalar() or 0

    # Fallback count
    fallback_stmt = select(func.count(InsightExecution.id)).where(
        InsightExecution.user_id == user.id,
        InsightExecution.status == "fallback"
    )
    fallback_count = (await db.execute(fallback_stmt)).scalar() or 0

    # Failed count
    failed_stmt = select(func.count(InsightExecution.id)).where(
        InsightExecution.user_id == user.id,
        InsightExecution.status == "failed"
    )
    failed_count = (await db.execute(failed_stmt)).scalar() or 0

    # Avg execution time (seconds)
    avg_time_stmt = select(
        func.avg(
            func.extract(
                'epoch',
                InsightExecution.completed_at - InsightExecution.started_at
            )
        )
    ).where(
        InsightExecution.user_id == user.id,
        InsightExecution.completed_at.isnot(None),
        InsightExecution.started_at.isnot(None),
    )
    avg_time = (await db.execute(avg_time_stmt)).scalar() or 0

    # Cache hit rate (reused executions)
    cached_stmt = select(func.count(InsightExecution.id)).where(
        InsightExecution.user_id == user.id,
        InsightExecution.status == "success",
    )
    cached_count = (await db.execute(cached_stmt)).scalar() or 0

    # Artifact count
    artifact_stmt = select(func.count(Insight.id)).where(
        Insight.user_id == user.id
    )
    artifact_count = (await db.execute(artifact_stmt)).scalar() or 0

    # Compute rates
    success_rate = round(success_count / total, 2) if total > 0 else 0.0
    fallback_rate = round(fallback_count / total, 2) if total > 0 else 0.0
    cache_hit_rate = round(cached_count / total, 2) if total > 0 else 0.0

    return {
        "executions": {
            "total": total,
            "success": success_count,
            "fallback": fallback_count,
            "failed": failed_count,
        },
        "rates": {
            "success_rate": success_rate,
            "fallback_rate": fallback_rate,
            "cache_hit_rate": cache_hit_rate,
        },
        "performance": {
            "avg_execution_time_seconds": round(float(avg_time), 2),
        },
        "artifacts": {
            "total": artifact_count,
        }
    }