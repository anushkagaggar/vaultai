import hashlib
from sqlalchemy import select, func
from app.models.expense import Expense
from app.models.rag_document import RagDocument


async def compute_source_hash(db, user_id: int,
                              pipeline_version: str,
                              prompt_version: str,
                              model_version: str,
                              embedding_version: str):

    # ---- Expenses fingerprint ----
    expense_stmt = select(
        func.count(Expense.id),
        func.max(Expense.updated_at)
    ).where(Expense.user_id == user_id)

    exp_count, exp_last = (await db.execute(expense_stmt)).one()

    # ---- RagDocuments fingerprint ----
    doc_stmt = select(
        func.count(RagDocument.id),
        func.max(RagDocument.updated_at)
    ).where(RagDocument.user_id == user_id)

    doc_count, doc_last = (await db.execute(doc_stmt)).one()

    payload = f"""
    exp_count:{exp_count}
    exp_last:{exp_last}
    doc_count:{doc_count}
    doc_last:{doc_last}
    pipeline:{pipeline_version}
    prompt:{prompt_version}
    model:{model_version}
    embed:{embedding_version}
    """

    return hashlib.sha256(payload.encode()).hexdigest()
