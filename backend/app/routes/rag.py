from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.vectordb.qdrant_client import insert_chunk, search_chunks
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/rag", tags=["RAG"])


# Fake embedding for now (384 dims)
def fake_embedding():

    return [0.01] * 384


@router.post("/debug-insert")
def debug_insert(user=Depends(get_current_user)):

    payload = {
        "user_id": user.id,
        "doc_id": 1,
        "version": 1,
        "trust": 0.9,
        "active": True,
        "filename": "test.txt",
        "chunk_index": 0,
        "text": "This is a test financial document."
    }

    insert_chunk(fake_embedding(), payload)

    return {"status": "inserted"}


@router.get("/debug-search")
def debug_search(user=Depends(get_current_user)):

    results = search_chunks(
        fake_embedding(),
        user.id
    )

    return {
        "count": len(results.points),
        "results": [
            {
                "score": r.score,
                "payload": r.payload
            }
            for r in results.points
        ]
    }
