from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Literal, Optional

from app.models.insight import Insight
from app.orchestrator.hashing import build_source_hash

import logging
logger = logging.getLogger(__name__)


class InsightStatus:
    """Status codes for insight resolution"""
    READY = "ready"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


async def resolve_insight(
    db: AsyncSession,
    user_id: int,
    insight_type: str,
    pipeline_version: str = "3.0",
    prompt_version: str = "1.1"
) -> dict:
    """
    Resolve the best available artifact for a user + insight type.
    
    This is the READ path - it NEVER triggers computation.
    
    Decision logic (strict order):
    1. Find latest artifact (SUCCESS preferred over FALLBACK)
    2. Check if artifact is fresh (source_hash matches current state)
    3. Return appropriate status
    
    Returns:
        dict with structure:
        - status: "ready" | "stale" | "unavailable"
        - degraded: bool (only if ready)
        - confidence: float (only if ready)
        - data: dict (only if ready)
        - execution_required: bool (only if stale)
    """
    
    # =====================================================
    # STEP 1: Find latest artifact (prefer SUCCESS)
    # =====================================================
    
    stmt = select(Insight).where(
        Insight.user_id == user_id,
        Insight.type == insight_type
    ).order_by(
        # Prefer SUCCESS over FALLBACK
        Insight.status.desc(),
        Insight.created_at.desc()
    ).limit(1)
    
    result = await db.execute(stmt)
    artifact = result.scalar_one_or_none()
    
    # =====================================================
    # CASE C: No artifact exists
    # =====================================================
    
    if not artifact:
        logger.info(f"No artifact found for user={user_id}, type={insight_type}")
        return {
            "status": InsightStatus.UNAVAILABLE,
            "message": "No insight computed yet. Use POST to start computation."
        }
    
    # =====================================================
    # STEP 2: Check freshness (recompute current hash)
    # =====================================================
    
    current_hash = await build_source_hash(
        db=db,
        user_id=user_id,
        insight_type=insight_type,
        pipeline_version=pipeline_version,
        prompt_version=prompt_version,
        model_version="phi3:mini",
        embedding_version="v1"
    )
    
    # Hash mismatch = data changed since artifact creation
    if artifact.source_hash != current_hash:
        logger.info(
            f"Artifact {artifact.id} is stale. "
            f"Hash mismatch: {artifact.source_hash[:8]} != {current_hash[:8]}"
        )
        return {
            "status": InsightStatus.STALE,
            "execution_required": True,
            "message": "Data changed. Use POST to recompute insight."
        }
    
    # =====================================================
    # CASE A: SUCCESS artifact (fresh)
    # =====================================================
    
    if artifact.status == "success":
        logger.info(f"Returning fresh SUCCESS artifact {artifact.id}")
        return {
            "status": InsightStatus.READY,
            "degraded": False,
            "confidence": artifact.confidence or 0.0,
            "data": {
                "summary": artifact.summary,
                "explanation": artifact.summary,  # Use summary as explanation
                "metrics": artifact.metrics,
            },
            "artifact_id": artifact.id,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None
        }
    
    # =====================================================
    # CASE B: FALLBACK artifact (degraded but usable)
    # =====================================================
    
    if artifact.status == "fallback":
        logger.info(f"Returning fresh FALLBACK artifact {artifact.id}")
        return {
            "status": InsightStatus.READY,
            "degraded": True,  # Mark as degraded quality
            "confidence": artifact.confidence or 0.0,
            "data": {
                "summary": artifact.summary,
                "explanation": None,  # No reliable explanation
                "metrics": artifact.metrics,
            },
            "artifact_id": artifact.id,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
            "message": "Degraded insight: metrics available but explanation unavailable."
        }
    
    # =====================================================
    # CASE C: SUPPRESSED or unknown status
    # =====================================================
    
    # Suppressed artifacts shouldn't exist, but handle gracefully
    logger.warning(f"Artifact {artifact.id} has unexpected status: {artifact.status}")
    return {
        "status": InsightStatus.UNAVAILABLE,
        "message": "No valid insight available."
    }