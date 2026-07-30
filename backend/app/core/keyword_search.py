# BM25 index + search

import re

from rank_bm25 import BM25Okapi

from app.db.models import Chunk
from app.db.session import SessionLocal

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def bm25_search(document_id: str, query: str, top_k: int = 20) -> list[tuple[str, float]]:
    """Keyword search scoped to one document's chunks. Builds the BM25 index
    fresh per call -- simplest correct approach at book-sized corpora; would
    be worth caching per document if this ever becomes a hot path.

    Returns (chunk_id, score) sorted descending.
    """
    session = SessionLocal()
    try:
        chunks = session.query(Chunk).filter_by(document_id=document_id).all()
    finally:
        session.close()

    if not chunks:
        return []

    corpus_ids = [chunk.id for chunk in chunks]
    tokenized_corpus = [_tokenize(chunk.text) for chunk in chunks]
    bm25 = BM25Okapi(tokenized_corpus)

    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(corpus_ids, scores), key=lambda pair: pair[1], reverse=True)
    return ranked[:top_k]
