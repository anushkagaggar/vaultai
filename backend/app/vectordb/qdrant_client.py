from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    PointStruct,
)

import uuid


QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

COLLECTION_NAME = "vaultai_rag"
VECTOR_SIZE = 384


def get_qdrant_client():
    return QdrantClient(
    url=f"http://{QDRANT_HOST}:{QDRANT_PORT}"
)


def init_collection():

    client = get_qdrant_client()

    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if COLLECTION_NAME in names:
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,

        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE
        )
    )


# --------------------------
# Insert Vector
# --------------------------

def insert_chunk(
    vector: list[float],
    payload: dict
):

    client = get_qdrant_client()

    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload=payload
    )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[point]
    )


# --------------------------
# Search Vectors
# --------------------------

def search_chunks(
    vector: list[float],
    user_id: int,
    limit: int = 5
):

    client = get_qdrant_client()

    search_filter = Filter(
        must=[
            FieldCondition(
                key="user_id",
                match=MatchValue(value=user_id)
            ),
            FieldCondition(
                key="active",
                match=MatchValue(value=True)
            )
        ]
    )

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=search_filter,
        limit=limit
    )

    return results

# --------------------------
# Batch Insert
# --------------------------

def insert_chunks_batch(vectors, payloads):

    client = get_qdrant_client()

    points = []

    for v, p in zip(vectors, payloads):

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=v,
                payload=p
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )
