from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.insight_service import generate_trends_insight
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("/trends")
def get_trends(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):

    insight = generate_trends_insight(db, user.id)

    return {
        "id": insight.id,
        "type": insight.type,
        "summary": insight.summary,
        "metrics": insight.metrics,
        "confidence": insight.confidence,
        "created_at": insight.created_at
    }
