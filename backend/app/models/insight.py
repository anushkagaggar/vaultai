from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    func
)

from app.models.base import Base


class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    type = Column(String(50), nullable=False)

    summary = Column(Text, nullable=False)

    metrics = Column(JSON, nullable=False)

    confidence = Column(Float, nullable=False)

    source_hash = Column(String(128), nullable=False)

    created_at = Column(DateTime, server_default=func.now())
