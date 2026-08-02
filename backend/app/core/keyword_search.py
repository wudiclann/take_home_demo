# BM25 index + search -- the keyword-matching half of hybrid retrieval.
# BM25 索引与检索——混合检索中负责关键词匹配的那一半。

import re

from rank_bm25 import BM25Okapi

from app.db.models import Chunk
from app.db.session import SessionLocal

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercases and splits text into alphanumeric tokens for BM25.
    将文本转为小写并切分为字母数字token，供 BM25 使用。"""
    return _TOKEN_RE.findall(text.lower())


def bm25_search(document_id: str, query: str, top_k: int = 20) -> list[tuple[str, float]]:
    """Keyword search scoped to one document's chunks. Builds the BM25 index
    fresh per call -- simplest correct approach at book-sized corpora; would
    be worth caching per document if this ever becomes a hot path.

    Returns (chunk_id, score) sorted descending.

    对单个文档的文本块做关键词检索。每次调用都重新构建 BM25 索引——在书籍
    量级的语料下这是最简单、正确的做法；如果这里成为性能瓶颈，值得考虑
    按文档缓存索引。

    返回按分数降序排列的 (chunk_id, score) 列表。
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
