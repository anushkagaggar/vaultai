import re

NUMBER_REGEX = r"\b\d+(?:\.\d+)?\b"

def extract_numbers_from_rag(context_chunks: list[str]) -> set[float]:
    allowed = set()

    for chunk in context_chunks:
        for n in re.findall(NUMBER_REGEX, chunk):
            try:
                allowed.add(float(n))
            except:
                pass

    return allowed
