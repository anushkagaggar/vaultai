from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.models.base import Base


class Insight(Base):
    """
    Durable artifact representing a validated execution result.
    
    An Insight is NOT the same as an Execution:
    - Execution = temporary computation record
    - Insight = stable, trusted knowledge derived from execution
    
    Lifecycle:
    - Created only after execution reaches SUCCESS state
    - Immutable once created
    - Reused when source_hash matches (same state of world)
    """
    
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core identity
    user_id = Column(Integer, nullable=False, index=True)
    type = Column(String(50), nullable=False)  # e.g., "trends", "risks"
    
    # Content
    summary = Column(String(2000), nullable=False)  # LLM explanation
    metrics = Column(JSON, nullable=False)  # Analytics snapshot
    
    # Lineage (NEW)
    execution_id = Column(Integer, ForeignKey('insight_executions.id'), nullable=True)
    status = Column(String(20), nullable=True)  # "success" or "fallback"
    pipeline_version = Column(String(20), nullable=True)
    
    # State fingerprint
    source_hash = Column(String(64), nullable=False, index=True)
    
    # Metadata
    confidence = Column(Float, default=0.8)
    created_at = Column(DateTime, server_default=func.now())
    
    # ✅ Uniqueness: One artifact per state of world
    __table_args__ = (
        UniqueConstraint('user_id', 'type', 'source_hash', name='uq_insight_state'),
    )