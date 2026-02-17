from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.expense import Expense
from app.confidence.scorer import ConfidenceInput


async def collect_confidence_inputs(
    db: AsyncSession,
    user_id: int,
    metrics: dict,
    classification: str
) -> ConfidenceInput:
    """
    Collect all data needed for confidence scoring.
    Queries DB for transaction count and date range.
    """

    # Query expense metadata
    stmt = select(
        func.count(Expense.id),
        func.min(Expense.expense_date),
        func.max(Expense.expense_date)
    ).where(Expense.user_id == user_id)

    result = await db.execute(stmt)
    total_transactions, first_date, last_date = result.one()

    # Convert dates to datetime
    def to_datetime(d):
        if d is None:
            return None
        if isinstance(d, datetime):
            return d
        return datetime.combine(d, datetime.min.time())

    return ConfidenceInput(
        total_transactions=total_transactions or 0,
        first_expense_at=to_datetime(first_date),
        last_expense_at=to_datetime(last_date),
        current_month=float(metrics["monthly"].get("current_month", 0)),
        previous_month=float(metrics["monthly"].get("previous_month", 0)),
        classification=classification
    )