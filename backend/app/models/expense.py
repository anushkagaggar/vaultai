from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.models.base import Base


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

    category = Column(String(100), nullable=False)

    description = Column(String(255))

    expense_date = Column(Date, nullable=False)

    extra_data = Column(JSON)

    user = relationship("User", backref="expenses")
