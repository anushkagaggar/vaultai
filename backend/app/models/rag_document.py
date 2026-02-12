from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    func
)

from app.models.base import Base


class RagDocument(Base):

    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    filename = Column(String(255), nullable=False)

    version = Column(Integer, nullable=False)

    trust_level = Column(Float, nullable=False)

    content_hash = Column(String(128), nullable=False)   # NEW
    active = Column(Boolean, default=True)

    uploaded_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # NEW
