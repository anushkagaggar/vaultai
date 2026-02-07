import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.analytics.trends import build_trends_report
from app.models.insight import Insight
from app.models.expense import Expense
from app.llm.client import generate_explanation
from app.insights.validator import validate_explanation

# -------------------------
# Dataset Hash
# -------------------------

async def compute_source_hash(db: AsyncSession, user_id: int):

    stmt = select(
        Expense.id,
        Expense.amount,
        Expense.category,
        Expense.expense_date
    ).where(Expense.user_id == user_id)

    result = await db.execute(stmt)

    rows = result.all()

    payload = [
        {
            "id": r.id,
            "amount": float(r.amount),
            "category": r.category,
            "date": str(r.expense_date)
        }
        for r in rows
    ]

    raw = json.dumps(payload, sort_keys=True)

    return hashlib.sha256(raw.encode()).hexdigest()


# -------------------------
# Main Generator
# -------------------------

async def generate_trends_insight(db: AsyncSession, user_id: int):

    source_hash = await compute_source_hash(db, user_id)

    # Check cache
    stmt = select(Insight).where(
        Insight.user_id == user_id,
        Insight.type == "trends",
        Insight.source_hash == source_hash
    )

    result = await db.execute(stmt)

    cached = result.scalars().first()

    if cached:
        return cached


    # Run analytics
    metrics = await build_trends_report(db, user_id)

    # Build prompt
    prompt = f"""
    You are given verified financial metrics.

    You MUST use only these numbers.

    Rolling averages:
    {metrics['rolling']}

    Monthly comparison:
    {metrics['monthly']}

    Top categories:
    {metrics['categories']}

    Trend type:
    {metrics['trend_type']}

    Rules:
    - Do NOT round numbers
    - Do NOT estimate
    - Do NOT rephrase percentages
    - Copy numbers exactly
    - No advice

    Write a 3–4 sentence explanation.
    """

    # Call LLM
    explanation = await generate_explanation(prompt)

    # Validate output
    is_valid = validate_explanation(explanation, metrics)

    if not is_valid:
        explanation = "NA"


    insight = Insight(
        user_id=user_id,
        type="trends",
        summary=explanation,
        metrics=metrics,
        confidence=0.8,
        source_hash=source_hash
    )

    db.add(insight)
    await db.commit()
    await db.refresh(insight)

    return insight
