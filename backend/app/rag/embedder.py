from sentence_transformers import SentenceTransformer


# Load once (important for speed)
_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Convert list of texts to embeddings.
    """

    vectors = _model.encode(
        texts,
        normalize_embeddings=True
    )

    return vectors.tolist()
