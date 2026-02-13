from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, JSON, Index, CheckConstraint
from sqlalchemy.orm import relationship
from datetime import date

from app.models.base import Base
from sqlalchemy.sql import func
from sqlalchemy import DateTime


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    amount = Column(Float, nullable=False)
    __table_args__ = (
    CheckConstraint("amount > 0", name="check_amount_positive"),
    Index("idx_expenses_user_date", "user_id", "expense_date"),
    )

    category = Column(String(100), nullable=False)

    description = Column(String(255))

    expense_date = Column(Date, default=date.today, nullable=False)

    extra_data = Column(JSON)

    user = relationship("User", backref="expenses")

    __table_args__ = (
    Index("idx_expenses_user_date", "user_id", "expense_date"),
    )
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
