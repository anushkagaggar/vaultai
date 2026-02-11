from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.insight_service import generate_trends_insight
from app.middleware.auth import get_current_user

from app.orchestrator import InsightRunner

router = APIRouter(prefix="/insights", tags=["Insights"])
runner = InsightRunner()

@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):

    result = await runner.run(db, user.id, "trends")

    return {
        "status": "started",
        "result": result
    }