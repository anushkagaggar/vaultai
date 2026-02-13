from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    JSON,
)

from app.models.base import Base


class InsightExecution(Base):

    __tablename__ = "insight_executions"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, nullable=False)
    insight_type = Column(String(50), nullable=False)

    pipeline_version = Column(String(20))
    prompt_template_version = Column(String(20))

    model_version = Column(String(50))
    embedding_version = Column(String(50))

    analytics_snapshot = Column(JSON)
    rag_snapshot = Column(JSON)
    prompt_snapshot = Column(Text)

    status = Column(String(20), nullable=False)

    source_hash = Column(String(64), nullable=False)

    cancel_requested = Column(Boolean, default=False)

    error_code = Column(String(50))
    error_message = Column(Text)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    step_failed = Column(String(50))

    llm_output = Column(Text)