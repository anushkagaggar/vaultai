from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.insight_service import generate_trends_insight
from app.middleware.auth import get_current_user

from app.orchestrator import InsightRunner
from app.orchestrator.response_mapper import map_execution_to_http

router = APIRouter(prefix="/insights", tags=["Insights"])
runner = InsightRunner()

@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    execution, result = await runner.run(db, user.id, "trends")

    return map_execution_to_http(execution, result)
