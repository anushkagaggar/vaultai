from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.insight_service import generate_trends_insight
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):

    insight = await generate_trends_insight(db, user.id)

    return {
        "id": insight.id,
        "type": insight.type,
        "summary": insight.summary,
        "metrics": insight.metrics,
        "confidence": insight.confidence,
        "created_at": insight.created_at
    }
