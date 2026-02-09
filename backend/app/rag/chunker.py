def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100
):
    """
    Split text into overlapping chunks.
    """

    chunks = []

    start = 0
    length = len(text)

    while start < length:

        end = start + chunk_size

        chunk = text[start:end]

        chunks.append(chunk.strip())

        start = end - overlap

        if start < 0:
            start = 0


    return [c for c in chunks if c]
