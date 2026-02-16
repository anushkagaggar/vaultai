from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.insight import Insight
from app.models.execution import InsightExecution
from app.orchestrator.state import State

import logging
logger = logging.getLogger(__name__)


async def create_artifact_from_execution(
    db: AsyncSession,
    execution: InsightExecution,
    result_json: dict
) -> Insight | None:
    """
    Convert a SUCCESS execution into a durable Insight artifact.
    
    Rules:
    - Only creates for SUCCESS executions
    - Deduplicates by (user_id, type, source_hash)
    - Does NOT modify execution
    - Returns existing if already exists
    
    Args:
        db: Database session
        execution: The execution that completed
        result_json: The result dictionary from runner
    
    Returns:
        Insight artifact or None if not created
    """
    
    # ✅ Rule 1: Only create for SUCCESS
    if execution.status != State.SUCCESS:
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
    
    # ✅ Rule 3: Create new artifact
    try:
        artifact = Insight(
            user_id=execution.user_id,
            type=execution.insight_type,
            summary=execution.llm_output,
            metrics=execution.analytics_snapshot,
            execution_id=execution.id,
            status=execution.status,  # "success"
            pipeline_version=execution.pipeline_version,
            source_hash=execution.source_hash,
            confidence=0.8,  # Placeholder for now
        )
        
        db.add(artifact)
        await db.commit()
        await db.refresh(artifact)
        
        logger.info(f"Created artifact {artifact.id} from execution {execution.id}")
        return artifact
        
    except IntegrityError as e:
        # Race condition: another request created it between check and insert
        await db.rollback()
        logger.warning(f"Artifact creation race for execution {execution.id}, fetching existing")
        
        # Fetch the one that was created
        result = await db.execute(stmt)
        return result.scalar_one()
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create artifact for execution {execution.id}: {e}")
        # ✅ Don't crash - just log and return None
        return None


async def get_artifact_by_hash(
    db: AsyncSession,
    user_id: int,
    insight_type: str,
    source_hash: str
) -> Insight | None:
    """
    Retrieve artifact by state fingerprint.
    Used for cache lookups.
    """
    stmt = select(Insight).where(
        Insight.user_id == user_id,
        Insight.type == insight_type,
        Insight.source_hash == source_hash
    )
    
    result = await db.execute(stmt)
    return result.scalar_one_or_none()