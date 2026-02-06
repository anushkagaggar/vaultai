from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.expense import Expense


# ----------------------------
# Rolling Averages
# ----------------------------

async def rolling_averages(
    db: AsyncSession,
    user_id: int,
    today: date = date.today()
):

    windows = [30, 60, 90]
    result = {}

    for days in windows:
        start = today - timedelta(days=days)

        stmt = async_select_avg = (
            select(func.avg(Expense.amount))
            .where(
                Expense.user_id == user_id,
                Expense.expense_date >= start,
                Expense.expense_date <= today
            )
        )

        res = await db.execute(stmt)

        avg_val = res.scalar()

        result[f"{days}_day_avg"] = round(avg_val or 0, 2)

    return result


# ----------------------------
# Month Comparison
# ----------------------------

async def monthly_comparison(
    db: AsyncSession,
    user_id: int,
    today: date = date.today()
):

    current_start = today.replace(day=1)

    prev_end = current_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)


    # Current
    stmt1 = select(func.sum(Expense.amount)).where(
        Expense.user_id == user_id,
        Expense.expense_date >= current_start,
        Expense.expense_date <= today
    )

    res1 = await db.execute(stmt1)
    current_total = res1.scalar() or 0


    # Previous
    stmt2 = select(func.sum(Expense.amount)).where(
        Expense.user_id == user_id,
        Expense.expense_date >= prev_start,
        Expense.expense_date <= prev_end
    )

    res2 = await db.execute(stmt2)
    prev_total = res2.scalar() or 0


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

async def top_categories(
    db: AsyncSession,
    user_id: int,
    limit: int = 5
):

    stmt = (
        select(
            Expense.category,
            func.sum(Expense.amount).label("total")
        )
        .where(Expense.user_id == user_id)
        .group_by(Expense.category)
        .order_by(func.sum(Expense.amount).desc())
        .limit(limit)
    )

    res = await db.execute(stmt)

    rows = res.all()

    return [
        {
            "category": r.category,
            "total": round(r.total, 2)
        }
        for r in rows
    ]

# ----------------------------
# Trend Classification
# ----------------------------

def classify_trend(monthly_data: dict):

    pct = monthly_data.get("percent_change")

    if pct is None:
        return "insufficient_data"

    if abs(pct) < 5:
        return "stable"

    if 5 <= pct < 50:
        return "moderate_increase"

    if pct >= 50:
        return "spike"

    if pct <= -20:
        return "drop"

    return "volatile"

# ----------------------------
# Main Generator
# ----------------------------

async def build_trends_report(db: AsyncSession, user_id: int):

    monthly = await monthly_comparison(db, user_id)

    return {
        "rolling": await rolling_averages(db, user_id),
        "monthly": monthly,
        "trend_type": classify_trend(monthly),
        "categories": await top_categories(db, user_id)
    }
