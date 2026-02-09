from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.vectordb.qdrant_client import insert_chunk, search_chunks
from app.middleware.auth import get_current_user
from app.models.rag_document import RagDocument
from app.database import get_db

import os
import hashlib
from datetime import datetime

router = APIRouter(prefix="/rag", tags=["RAG"])
UPLOAD_DIR = "uploads"

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


@router.post("/upload")
async def upload_doc(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):

    # 1. Create user dir
    user_dir = os.path.join(UPLOAD_DIR, str(user.id))
    os.makedirs(user_dir, exist_ok=True)

    # 2. Save file
    path = os.path.join(user_dir, file.filename)

    content = await file.read()

    with open(path, "wb") as f:
        f.write(content)

    # 3. Hash file
    file_hash = hashlib.sha256(content).hexdigest()

    # 4. Versioning
    result = await db.execute(
        text("""
            SELECT MAX(version)
            FROM rag_documents
            WHERE user_id = :uid AND filename = :fn
        """),

        {"uid": user.id, "fn": file.filename}
    )

    max_ver = result.scalar() or 0
    version = max_ver + 1

    # 5. Trust (initial heuristic)
    trust = 0.7

    doc = RagDocument(
        user_id=user.id,
        filename=file.filename,
        version=version,
        trust_level=trust,
        hash=file_hash,
        active=True
    )

    db.add(doc)
    await db.commit()
    await db.refresh(doc) 

    return {
        "doc_id": doc.id,
        "filename": file.filename,
        "version": version,
        "trust": trust
    }