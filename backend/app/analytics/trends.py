from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.expense import Expense


# ----------------------------
# Rolling Averages
# ----------------------------

def rolling_averages(
    db: Session,
    user_id: int,
    today: date = date.today()
):
    windows = [30, 60, 90]
    result = {}

    for days in windows:
        start = today - timedelta(days=days)

        avg_val = (
            db.query(func.avg(Expense.amount))
            .filter(
                Expense.user_id == user_id,
                Expense.expense_date >= start,
                Expense.expense_date <= today
            )
            .scalar()
        )

        result[f"{days}_day_avg"] = round(avg_val or 0, 2)

    return result


# ----------------------------
# Month Comparison
# ----------------------------

def monthly_comparison(db: Session, user_id: int, today: date = date.today()):

    current_start = today.replace(day=1)

    prev_end = current_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)

    current_total = (
        db.query(func.sum(Expense.amount))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date >= current_start,
            Expense.expense_date <= today
        )
        .scalar()
        or 0
    )

    prev_total = (
        db.query(func.sum(Expense.amount))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date >= prev_start,
            Expense.expense_date <= prev_end
        )
        .scalar()
        or 0
    )

    pct = None

    if prev_total > 0:
        pct = round(
            ((current_total - prev_total) / prev_total) * 100,
            2
        )

    return {
        "current_month": round(current_total, 2),
        "previous_month": round(prev_total, 2),
        "percent_change": pct
    }


# ----------------------------
# Category Totals
# ----------------------------

def top_categories(db: Session, user_id: int, limit: int = 5):

    rows = (
        db.query(
            Expense.category,
            func.sum(Expense.amount).label("total")
        )
        .filter(Expense.user_id == user_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "category": r.category,
            "total": round(r.total, 2)
        }
        for r in rows
    ]


# ----------------------------
# Main Generator
# ----------------------------

def build_trends_report(db: Session, user_id: int):

    return {
        "rolling": rolling_averages(db, user_id),
        "monthly": monthly_comparison(db, user_id),
        "categories": top_categories(db, user_id)
    }
