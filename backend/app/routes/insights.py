from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.orchestrator import InsightRunner

router = APIRouter(prefix="/insights", tags=["Insights"])
runner = InsightRunner()

@router.post("/trends")
async def start_trends(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    execution, result = await runner.run(db, user.id, "trends")

    # If reusable finished execution exists (cached)
    if execution.status == "success":
        return {
            "status": "ready",
            "execution_id": execution.id,
            "cached": True,
            "data": {
                "metrics": result["metrics"],
                "explanation": result["explanation"],
            }
        }

    # Job created (new execution)
    return {
        "status": execution.status,  # ✅ Changed from execution.status
        "execution_id": execution.id,
        "cached": False,
    }