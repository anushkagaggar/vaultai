from app.rag.embedder import embed_texts
from app.vectordb.qdrant_client import search_chunks

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