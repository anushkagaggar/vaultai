from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.insight import Insight
from app.models.execution import InsightExecution
from app.orchestrator.state import State
from app.confidence.scorer import compute_confidence 
from app.confidence.collector import collect_confidence_inputs

import logging
logger = logging.getLogger(__name__)


async def create_artifact_from_execution(
    db: AsyncSession,
    execution: InsightExecution,
    result_json: dict
) -> Insight | None:
    """
    Convert a completed execution into a durable Insight artifact.
    
    Rules:
    - SUCCESS: Create full artifact with explanation
    - FALLBACK: Create degraded artifact (metrics only, no explanation)
    - FAILED/SUPPRESSED: Do not create artifact
    
    Args:
        db: Database session
        execution: The execution that completed
        result_json: The result dictionary from runner
    
    Returns:
        Insight artifact or None if not created
    """
    
    # ✅ Rule 1: Only create for SUCCESS or FALLBACK
    if execution.status not in [State.SUCCESS, State.FALLBACK]:
        logger.info(f"Skipping artifact creation for execution {execution.id} (status: {execution.status})")
        return None
    
    # ✅ Rule 2: Check if artifact already exists
    stmt = select(Insight).where(
        Insight.user_id == execution.user_id,
        Insight.type == execution.insight_type,
        Insight.source_hash == execution.source_hash
    )
    
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        logger.info(f"Artifact already exists for execution {execution.id}, reusing artifact {existing.id}")
        return existing
    
    # ✅ Compute confidence score
    try:
        metrics = execution.analytics_snapshot or {}
        inputs = await collect_confidence_inputs(
            db=db,
            user_id=execution.user_id,
            metrics=metrics,
            classification=execution.status  # "success" or "fallback"
        )
        
        breakdown = compute_confidence(inputs)
        confidence = breakdown.final_confidence
        
        logger.info(
            f"Confidence for execution {execution.id}: {confidence} "
            f"(cov={breakdown.coverage_score}, "
            f"win={breakdown.window_score}, "
            f"stab={breakdown.stability_score}, "
            f"exp={breakdown.explanation_score})"
        )
        
    except Exception as e:
        logger.error(f"Confidence scoring failed for execution {execution.id}: {e}")
        confidence = 0.0  # Safe default
    
    # ✅ Rule 3: Create new artifact (SUCCESS or FALLBACK)
    try:
        # For FALLBACK: Use degraded explanation
        if execution.status == State.FALLBACK:
            summary = "Spending trend detected. Metrics available but detailed explanation unavailable due to validation."
        else:
            summary = execution.llm_output
        
        artifact = Insight(
            user_id=execution.user_id,
            type=execution.insight_type,
            summary=summary,
            metrics=execution.analytics_snapshot,
            execution_id=execution.id,
            status=execution.status,  # "success" or "fallback"
            pipeline_version=execution.pipeline_version,
            source_hash=execution.source_hash,
            confidence=confidence
        )
        
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        
        logger.info(
            f"Created artifact {artifact.id} "
            f"(status={execution.status}, confidence={confidence})"
        )
        return artifact
        
    except IntegrityError as e:
        # Race condition: another request created it
        await db.rollback()
        logger.warning(f"Artifact creation race for execution {execution.id}, fetching existing")
        
        result = await db.execute(stmt)
        return result.scalar_one()
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create artifact for execution {execution.id}: {e}")
        return None


async def get_artifact_by_hash(
    db: AsyncSession,
    user_id: int,
    insight_type: str,
    source_hash: str
) -> Insight | None:
    """
    Retrieve artifact by state fingerprint.
    Returns most recent artifact (SUCCESS preferred over FALLBACK).
    """
    stmt = select(Insight).where(
        Insight.user_id == user_id,
        Insight.type == insight_type,
        Insight.source_hash == source_hash
    ).order_by(
        # Prefer SUCCESS over FALLBACK
        Insight.status.desc(),
        Insight.created_at.desc()
    ).limit(1)
    
    result = await db.execute(stmt)
    return result.scalar_one_or_none()