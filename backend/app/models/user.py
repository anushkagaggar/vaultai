from sqlalchemy import Column, Integer, String, Boolean, DateTime, func

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String(255), unique=True, nullable=False, index=True)

    password_hash = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    refresh_token = Column(String(255), nullable=True, index=True)

    refresh_token_expires_at = Column(DateTime(timezone=True), nullable=True)
