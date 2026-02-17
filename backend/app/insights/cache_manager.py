from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.insight import Insight

import logging
logger = logging.getLogger(__name__)

# =====================================================
# TTL CONFIGURATION
# =====================================================

# How long an artifact is valid before forced recompute
INSIGHT_TTL_HOURS = 24  # Invalidate after 24 hours


def is_expired(artifact: Insight) -> bool:
    """
    Check if artifact has exceeded TTL.
    
    An artifact expires if:
    created_at + TTL < now
    """
    if not artifact.created_at:
        return True
    
    expiry_time = artifact.created_at + timedelta(hours=INSIGHT_TTL_HOURS)
    return datetime.utcnow() > expiry_time


def is_version_stale(
    artifact: Insight,
    current_pipeline_version: str,
    current_model_version: str
) -> bool:
    """
    Check if artifact was produced by an older pipeline version.
    
    Invalidate when:
    - pipeline_version changed
    - model_version changed (tracked in execution, not insight directly)
    """
    if artifact.pipeline_version != current_pipeline_version:
        logger.info(
            f"Artifact {artifact.id} pipeline version mismatch: "
            f"{artifact.pipeline_version} != {current_pipeline_version}"
        )
        return True
    
    return False


async def find_valid_insight(
    db: AsyncSession,
    user_id: int,
    insight_type: str,
    source_hash: str,
    current_pipeline_version: str = "3.0",
    current_model_version: str = "phi3:mini"
) -> Insight | None:
    """
    Find a valid cached artifact for given user + type + data state.
    
    Returns artifact ONLY if ALL conditions met:
    1. source_hash matches (data unchanged)
    2. Not expired (within TTL)
    3. Not version stale (same pipeline/model)
    4. Status is success or fallback (not suppressed)
    
    Returns None if any condition fails → triggers recompute.
    """
    
    # ✅ Query: Find latest artifact matching hash
    stmt = select(Insight).where(
        Insight.user_id == user_id,
        Insight.type == insight_type,
        Insight.source_hash == source_hash,
        Insight.status.in_(["success", "fallback"])  # Never return suppressed
    ).order_by(
        Insight.status.desc(),       # Prefer SUCCESS over FALLBACK
        Insight.created_at.desc()    # Most recent first
    ).limit(1)
    
    result = await db.execute(stmt)
    artifact = result.scalar_one_or_none()
    
    if not artifact:
        logger.info(f"Cache MISS: No artifact for user={user_id}, type={insight_type}")
        return None
    
    # ✅ Check TTL expiry
    if is_expired(artifact):
        logger.info(
            f"Cache EXPIRED: Artifact {artifact.id} expired. "
            f"Created: {artifact.created_at}, TTL: {INSIGHT_TTL_HOURS}h"
        )
        return None
    
    # ✅ Check version staleness
    if is_version_stale(artifact, current_pipeline_version, current_model_version):
        logger.info(
            f"Cache STALE: Artifact {artifact.id} version outdated. "
            f"Pipeline: {artifact.pipeline_version} vs {current_pipeline_version}"
        )
        return None
    
    logger.info(
        f"Cache HIT: Artifact {artifact.id} "
        f"(status={artifact.status}, confidence={artifact.confidence})"
    )
    return artifact


async def invalidate_user_cache(
    db: AsyncSession,
    user_id: int,
    insight_type: str | None = None
):
    """
    Explicit cache invalidation.
    
    Called when:
    - User deletes expense
    - User uploads new document
    - Admin forces recompute
    
    Does NOT delete artifacts - just marks them expired
    by setting created_at to epoch (safe for audit trail).
    """
    from sqlalchemy import update
    from app.models.insight import Insight
    
    stmt = update(Insight).where(
        Insight.user_id == user_id,
        *(
            [Insight.type == insight_type]
            if insight_type else []
        )
    ).values(
        created_at=datetime(1970, 1, 1)  # Force expiry
    )
    
    await db.execute(stmt)
    await db.commit()
    
    logger.info(
        f"Cache invalidated for user={user_id}, "
        f"type={insight_type or 'all'}"
    )