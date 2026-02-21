from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from app.vectordb.qdrant_client import insert_chunk, search_chunks
from app.middleware.auth import get_current_user
from app.models.rag_document import RagDocument
from app.database import get_db
from app.rag.indexer import index_document
from app.rag.retriever import retrieve_context

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


# ═══════════════════════════════════════════════════════════════════════════
# ENHANCED: Upload with Better Error Handling
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/upload")
async def upload_doc(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Upload a document with comprehensive error handling.
    Returns document info with initial status.
    """
    
    try:
        # Validate file type
        allowed_types = ["application/pdf", "text/plain"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: PDF, TXT"
            )
        
        # 1. Create user dir
        user_dir = os.path.join(UPLOAD_DIR, str(user.id))
        os.makedirs(user_dir, exist_ok=True)

        # 2. Read file content
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # 3. Save file
        path = os.path.join(user_dir, file.filename)
        with open(path, "wb") as f:
            f.write(content)

        # 4. Hash file
        file_hash = hashlib.sha256(content).hexdigest()

        # 5. Versioning
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

        # 6. Trust (initial heuristic)
        trust = 0.7

        # 7. Create DB record
        doc = RagDocument(
            user_id=user.id,
            filename=file.filename,
            version=version,
            trust_level=trust,
            content_hash=file_hash,
            active=True
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # 8. Index document
        try:
            chunks = index_document(
                file_path=path,
                user_id=user.id,
                doc_id=doc.id,
                version=version,
                trust=trust,
                filename=file.filename
            )
        except Exception as e:
            # If indexing fails, mark document as inactive
            doc.active = False
            await db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Indexing failed: {str(e)}"
            )

        return {
            "id": doc.id,
            "filename": file.filename,
            "version": version,
            "trust_level": trust,
            "chunks_indexed": chunks,
            "status": "succeeded",
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/debug-retrieve")
def debug_retrieve(
    q: str,
    user=Depends(get_current_user)
):

    ctx = retrieve_context(q, user.id)

    return {
        "query": q,
        "results": ctx
    }

# ═══════════════════════════════════════════════════════════════════════════
# NEW: Get All Documents (with status)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/documents")
async def get_documents(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Get all documents uploaded by the current user.
    Returns list with status, trust level, version info.
    """
    
    stmt = select(RagDocument).where(
        RagDocument.user_id == user.id
    ).order_by(
        RagDocument.uploaded_at.desc()
    )
    
    result = await db.execute(stmt)
    docs = result.scalars().all()
    
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "version": doc.version,
            "trust_level": doc.trust_level,
            "active": doc.active,
            "content_hash": doc.content_hash,
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            "status": "succeeded" if doc.active else "inactive",  # Simple status
        }
        for doc in docs
    ]


# ═══════════════════════════════════════════════════════════════════════════
# NEW: Get Single Document Status
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/documents/{doc_id}/status")
async def get_document_status(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Get detailed status of a specific document.
    Useful for polling upload progress.
    """
    
    stmt = select(RagDocument).where(
        RagDocument.id == doc_id,
        RagDocument.user_id == user.id
    )
    
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if file exists on disk
    user_dir = os.path.join(UPLOAD_DIR, str(user.id))
    file_path = os.path.join(user_dir, doc.filename)
    file_exists = os.path.exists(file_path)
    
    # Determine status
    if doc.active and file_exists:
        status = "succeeded"
    elif not file_exists:
        status = "failed"
    else:
        status = "inactive"
    
    return {
        "id": doc.id,
        "filename": doc.filename,
        "version": doc.version,
        "status": status,
        "trust_level": doc.trust_level,
        "active": doc.active,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "file_exists": file_exists,
        "content_hash": doc.content_hash,
    }

# ═══════════════════════════════════════════════════════════════════════════
# NEW: Delete Document
# ═══════════════════════════════════════════════════════════════════════════

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Delete a document and its associated file.
    """
    
    stmt = select(RagDocument).where(
        RagDocument.id == doc_id,
        RagDocument.user_id == user.id
    )
    
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from disk
    user_dir = os.path.join(UPLOAD_DIR, str(user.id))
    file_path = os.path.join(user_dir, doc.filename)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            # Log but don't fail if file deletion fails
            print(f"Warning: Failed to delete file {file_path}: {e}")
    
    # Delete from database
    await db.delete(doc)
    await db.commit()
    
    return {
        "message": "Document deleted successfully",
        "id": doc_id
    }