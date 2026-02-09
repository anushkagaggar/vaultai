from app.rag.parser import parse_file
from app.rag.chunker import chunk_text
from app.rag.embedder import embed_texts
from app.vectordb.qdrant_client import insert_chunks_batch


def index_document(
    file_path: str,
    user_id: int,
    doc_id: int,
    version: int,
    trust: float,
    filename: str
):

    # 1. Parse
    text = parse_file(file_path)

    if not text.strip():
        return 0


    # 2. Chunk
    chunks = chunk_text(text)


    # 3. Embed
    vectors = embed_texts(chunks)


    # 4. Payloads
    payloads = []

    for i, chunk in enumerate(chunks):

        payloads.append({
            "user_id": user_id,
            "doc_id": doc_id,
            "version": version,
            "trust": trust,
            "active": True,
            "filename": filename,
            "chunk_index": i,
            "text": chunk
        })


    # 5. Store
    insert_chunks_batch(vectors, payloads)

    return len(chunks)
