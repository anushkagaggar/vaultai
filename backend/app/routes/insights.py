from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.orchestrator import InsightRunner
from app.orchestrator.state import State  # ✅ Import State

router = APIRouter(prefix="/insights", tags=["Insights"])
runner = InsightRunner()

@router.post("/trends")
async def start_trends(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    execution, result = await runner.run(db, user.id, "trends")

    # Cached success (terminal immediately)
    if execution.status == State.SUCCESS:
        return {
            "execution_id": execution.id,
            "status": "success",
            "is_terminal": True,  # ✅ No polling needed
            "cached": True,
            "result": {
                "metrics": result["metrics"],
                "explanation": result["explanation"],
            }
        }

    # Job created (non-terminal, needs polling)
    return {
        "execution_id": execution.id,
        "status": "accepted",
        "is_terminal": False,  # ✅ Client should poll
        "cached": False,
    }