# BM25 keyword search. It matches words, not meaning, so a question worded
# differently from the notes can miss.

import math
import re
from collections import Counter

from app.schemas.document import DocumentChunk

K1 = 1.5
B = 0.75
WORD = re.compile(r"\w+", re.UNICODE)
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i in is it its of on or "
    "that the this to was were what when where which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return WORD.findall(text.lower())


def select_chunks(chunks: list[DocumentChunk], query: str, top_k: int) -> list[DocumentChunk]:
    terms = set(tokenize(query))
    terms = (terms - STOPWORDS) or terms
    if not chunks or not terms:
        return []

    counts = [Counter(tokenize(chunk.text)) for chunk in chunks]
    lengths = [sum(count.values()) for count in counts]
    average = (sum(lengths) / len(lengths)) or 1.0
    total = len(chunks)
    containing = {term: sum(1 for count in counts if term in count) for term in terms}

    scored = []
    for chunk, count, length in zip(chunks, counts, lengths):
        score = 0.0
        for term in terms:
            frequency = count.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (total - containing[term] + 0.5) / (containing[term] + 0.5))
            score += idf * frequency * (K1 + 1) / (frequency + K1 * (1 - B + B * length / average))
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    best = [chunk for _, chunk in scored[:top_k]]
    return sorted(best, key=lambda chunk: chunk.chunk_number)
