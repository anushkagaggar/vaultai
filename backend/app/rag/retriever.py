from app.rag.embedder import embed_texts
from app.vectordb.qdrant_client import search_chunks
from app.models.rag_document import RagDocument
from sqlalchemy import select

async def retrieve_context(
    query: str,
    user_id: int,
    limit: int = 5
) -> list[str]:

    # 1. Embed query
    vector = embed_texts([query])[0]

    # 2. Search Qdrant
    results = search_chunks(
        vector=vector,
        user_id=user_id,
        limit=limit
    )

    contexts = []

    # FIX: Iterate over results.points, not results
    for point in results.points:
        if point.payload and "text" in point.payload:
            contexts.append(point.payload["text"])

    return contexts

async def get_rag_context(db, user_id: int) -> tuple[str, str]:
    """
    Returns:
    prompt_context -> formatted text for LLM
    raw_text -> raw document text for validator grounding
    """

    docs = await db.execute(
        select(RagDocument.content)
        .where(RagDocument.user_id == user_id, RagDocument.active == True)
        .order_by(RagDocument.updated_at.desc())
        .limit(5)
    )

    rows = docs.scalars().all()

    if not rows:
        return "", ""

    # what model sees
    prompt_context = "\n\n".join(rows)

    # what validator checks against (same but NOT summarized)
    raw_text = " ".join(rows)

    return prompt_context, raw_text
