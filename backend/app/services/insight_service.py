import hashlib
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.analytics.trends import build_trends_report
from app.models.insight import Insight
from app.models.expense import Expense
from app.llm.client import generate_explanation
from app.insights.validator import validate_explanation
from app.rag.retriever import retrieve_context

logger = logging.getLogger(__name__)


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

    # Retrieve RAG context
    rag_context = retrieve_context(
        query="user financial documents",
        user_id=user_id
    )

    rag_text = "\n\n".join(rag_context[:1])[:500]

    prompt = f"""
You are generating a financial insight.

STRICT RULES:
- Write EXACTLY 2 sentences
- Use ONLY numbers from the data below
- DO NOT add analysis, reports, or extra instructions
- DO NOT mention user IDs, document entries, or categories not in the data
- Stop after 2 sentences

Approved data:

Rolling averages:
30d={metrics['rolling']['30_day_avg']}
60d={metrics['rolling']['60_day_avg']}
90d={metrics['rolling']['90_day_avg']}

Monthly:
current={metrics['monthly']['current_month']}
previous={metrics['monthly']['previous_month']}
change={metrics['monthly']['percent_change']}

Categories:
{metrics['categories']}

Documents:
{rag_text}

Write exactly 2 sentences summarizing the spending trends.
"""

    # Call LLM
    # In insight_service.py, after generate_explanation:
    explanation = await generate_explanation(prompt)

    # Clean up the response - take only first 2 sentences or up to separator
    if "-----" in explanation or "---" in explanation:
        explanation = explanation.split("-----")[0].split("---")[0].strip()

    # Or limit to first 2 sentences
    sentences = explanation.split('. ')
    if len(sentences) > 2:
        explanation = '. '.join(sentences[:2]) + '.'

    logger.info(f"LLM generated explanation: {explanation[:200]}...")

    # Validate output - PASS RAG CONTEXT TOO
    is_valid = validate_explanation(explanation, metrics, rag_text)

    if not is_valid:
        logger.warning("Validation failed, using fallback")
        explanation = "Explanation suppressed due to unsupported claims."

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