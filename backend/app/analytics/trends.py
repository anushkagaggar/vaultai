from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.expense import Expense


# ---------------------------
# Rolling Averages
# ---------------------------

def get_rolling_means(
    db: Session,
    user_id: int,
    today: date = date.today()
):
    windows = [30, 60, 90]
    results = {}

    for days in windows:
        start_date = today - timedelta(days=days)

        avg_amount = (
            db.query(func.avg(Expense.amount))
            .filter(
                Expense.user_id == user_id,
                Expense.expense_date >= start_date,
                Expense.expense_date <= today
            )
            .scalar()
        )

        results[f"{days}_day_avg"] = round(avg_amount or 0, 2)

    return results


# ---------------------------
# Month over Month Change
# ---------------------------

def get_monthly_change(db: Session, user_id: int, today: date = date.today()):
    this_month_start = today.replace(day=1)

    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    this_month_sum = (
        db.query(func.sum(Expense.amount))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date >= this_month_start,
            Expense.expense_date <= today
        )
        .scalar()
        or 0
    )

    last_month_sum = (
        db.query(func.sum(Expense.amount))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date >= last_month_start,
            Expense.expense_date <= last_month_end
        )
        .scalar()
        or 0
    )

    if last_month_sum == 0:
        pct_change = None
    else:
        pct_change = round(
            ((this_month_sum - last_month_sum) / last_month_sum) * 100,
            2
        )

    return {
        "this_month": round(this_month_sum, 2),
        "last_month": round(last_month_sum, 2),
        "pct_change": pct_change
    }


# ---------------------------
# Category Trends
# ---------------------------

def get_category_trends(db: Session, user_id: int, limit: int = 5):
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


# ---------------------------
# Unified Trends Report
# ---------------------------

def generate_trends_report(db: Session, user_id: int):
    return {
        "rolling_means": get_rolling_means(db, user_id),
        "monthly_change": get_monthly_change(db, user_id),
        "category_trends": get_category_trends(db, user_id)
    }
