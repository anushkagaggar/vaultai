import hashlib
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.models.rag_document import RagDocument
from app.models.execution import InsightExecution
from app.orchestrator.state import State


# ---------------- EXPENSE FINGERPRINT ----------------
async def _expense_fingerprint(db: AsyncSession, user_id: int) -> str:
    """
    Detects:
    - new expense
    - deleted expense
    - edited expense
    """

    stmt = select(
        func.count(Expense.id),
        func.coalesce(func.max(Expense.updated_at), func.max(Expense.created_at))
    ).where(Expense.user_id == user_id)

    count, last_update = (await db.execute(stmt)).one()

    return f"{count}:{last_update}"


# ---------------- RAG FINGERPRINT ----------------
async def _rag_fingerprint(db: AsyncSession, user_id: int) -> str:
    """
    Detects:
    - new upload
    - delete
    - overwrite same filename
    - replace document content
    """

    stmt = select(
        func.count(RagDocument.id),
        func.coalesce(func.max(RagDocument.uploaded_at), "1970-01-01"),
        func.coalesce(func.sum(func.length(RagDocument.hash)), 0),
    ).where(
        RagDocument.user_id == user_id,
        RagDocument.active == True
    )

    count, last_upload, hash_mass = (await db.execute(stmt)).one()

    return f"{count}:{last_upload}:{hash_mass}"


# ---------------- SOURCE HASH ----------------
async def build_source_hash(
    db: AsyncSession,
    user_id: int,
    insight_type: str,
    pipeline_version: str,
    prompt_version: str,
    model_version: str,
    embedding_version: str,
) -> str:
    """
    Global deterministic fingerprint of the *state of knowledge*.
    If this hash matches → insight MUST be identical.
    """

    expense_sig = await _expense_fingerprint(db, user_id)
    rag_sig = await _rag_fingerprint(db, user_id)

    payload = (
        f"type={insight_type}|"
        f"expense={expense_sig}|"
        f"rag={rag_sig}|"
        f"pipeline={pipeline_version}|"
        f"prompt={prompt_version}|"
        f"model={model_version}|"
        f"embed={embedding_version}"
    )

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------- REUSE LOOKUP ----------------
async def find_reusable_execution(
    db: AsyncSession,
    user_id: int,
    insight_type: str,
    source_hash: str,
) -> InsightExecution | None:
    """
    Reuse only SUCCESS executions.
    Never reuse fallback / failed / running states.
    """

    stmt = (
        select(InsightExecution)
        .where(
            InsightExecution.user_id == user_id,
            InsightExecution.insight_type == insight_type,
            InsightExecution.source_hash == source_hash,
            InsightExecution.status == State.SUCCESS,
        )
        .order_by(InsightExecution.completed_at.desc())
        .limit(1)
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()
