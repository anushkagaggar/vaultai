from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

COLLECTION_NAME = "vaultai_rag"
VECTOR_SIZE = 384


def get_qdrant_client():

    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT
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
