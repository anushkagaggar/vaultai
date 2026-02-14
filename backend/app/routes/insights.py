from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.orchestrator import InsightRunner
from app.orchestrator.state import State
from app.validation.diagnostic import build_validation_report

router = APIRouter(prefix="/insights", tags=["Insights"])
runner = InsightRunner()

@router.post("/trends")
async def start_trends(
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    execution, result = await runner.run(db, user.id, "trends")

    # ✅ Check if execution reached terminal state
    if State.is_terminal(execution.status):
        
        # SUCCESS (cached)
        if execution.status == State.SUCCESS:
            return {
                "execution_id": execution.id,
                "status": "success",
                "is_terminal": True,
                "cached": True,
                "result": {
                    "metrics": result["metrics"],
                    "explanation": result["explanation"],
                }
            }
        
        # FALLBACK (cached degraded)
        elif execution.status == State.FALLBACK:
            # ✅ Rebuild validation report to see why it failed
            
            rag_text = "\n".join(execution.rag_snapshot) if execution.rag_snapshot else ""
            report = build_validation_report(
                execution.llm_output,
                execution.analytics_snapshot,
                rag_text
            )
            
            return {
                "execution_id": execution.id,
                "status": "fallback",
                "is_terminal": True,
                "cached": True,
                "result": result,
                "validation_debug": {  # ✅ Add debug info
                    "numbers_ok": report.numbers_ok,
                    "forbidden_language_ok": report.forbidden_language_ok,
                    "rag_supported": report.rag_supported,
                    "has_content": report.has_content,
                    "reasoning_quality": report.reasoning_quality,
                    "issues": report.issues,
                }
            }
        
        # FAILED
        elif execution.status == State.FAILED:
            return {
                "execution_id": execution.id,
                "status": "failed",
                "is_terminal": True,
                "error": execution.error_message,
                "error_code": execution.error_code,
            }
        
        # CANCELLED
        elif execution.status == State.CANCELLED:
            return {
                "execution_id": execution.id,
                "status": "cancelled",
                "is_terminal": True,
            }
    
    # ✅ Non-terminal (job is pending/running)
    return {
        "execution_id": execution.id,
        "status": "accepted",
        "is_terminal": False,
        "cached": False,
    }