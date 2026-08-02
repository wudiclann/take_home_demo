# RRF merge of BM25 + vector results, then cross-encoder rerank to the final top-k
# 用倒数排名融合（RRF）合并 BM25 与向量检索结果，再用交叉编码器重排序，得到最终 top-k

from dataclasses import dataclass

from app.core.embeddings import embed_texts
from app.core.keyword_search import bm25_search
from app.core.reranker import rerank
from app.core.vector_store import query_similar
from app.db.models import Chunk
from app.db.session import SessionLocal

RRF_K = 60


@dataclass
class RetrievedChunk:
    """One retrieved chunk plus both of its scores, for citations and the
    refusal-gate decision downstream.
    一个被检索到的文本块及其两项分数，供后续生成引用和判断是否拒答使用。"""

    chunk_id: str
    text: str
    chapter_id: str | None
    start_page: int | None
    end_page: int | None
    rrf_score: float
    rerank_score: float


def reciprocal_rank_fusion(*ranked_id_lists: list[str], k: int = RRF_K) -> list[tuple[str, float]]:
    """Each argument is a list of chunk ids in rank order (best first),
    joined by shared chunk id. Returns (chunk_id, rrf_score) sorted descending.

    每个参数都是一个按排名排序（最相关的在前）的 chunk id 列表，
    按相同的 chunk id 合并。返回按 rrf_score 降序排列的 (chunk_id, rrf_score)。
    """
    scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, chunk_id in enumerate(ranked_ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)


def hybrid_search(document_id: str, query: str, top_k: int = 20) -> list[tuple[str, float]]:
    """BM25 keyword search + Chroma vector search, scoped to one document,
    merged by Reciprocal Rank Fusion. Returns (chunk_id, rrf_score) sorted descending.

    对单个文档同时做 BM25 关键词检索和 Chroma 向量检索，
    再用倒数排名融合（RRF）合并两路结果。
    返回按 rrf_score 降序排列的 (chunk_id, rrf_score)。
    """
    [embedding] = embed_texts([query])

    bm25_results = bm25_search(document_id, query, top_k=top_k)
    bm25_ids = [chunk_id for chunk_id, _ in bm25_results]

    vector_results = query_similar(embedding, top_k=top_k, where={"document_id": document_id})
    vector_ids = vector_results["ids"][0]

    merged = reciprocal_rank_fusion(bm25_ids, vector_ids)
    return merged[:top_k]


def retrieve(document_id: str, query: str, hybrid_k: int = 20, final_k: int = 3) -> list[RetrievedChunk]:
    """Full retrieval pipeline: hybrid search -> cross-encoder rerank -> top final_k.
    完整检索流水线：混合检索 -> 交叉编码器重排序 -> 取最终的 top final_k 个结果。"""
    hybrid_results = hybrid_search(document_id, query, top_k=hybrid_k)
    if not hybrid_results:
        return []
    rrf_scores = dict(hybrid_results)
    chunk_ids = list(rrf_scores.keys())

    session = SessionLocal()
    try:
        chunks = session.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    finally:
        session.close()
    chunk_by_id = {chunk.id: chunk for chunk in chunks}

    candidates = [(cid, chunk_by_id[cid].text) for cid in chunk_ids if cid in chunk_by_id]
    reranked = rerank(query, candidates, top_k=final_k)

    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            text=chunk_by_id[chunk_id].text,
            chapter_id=chunk_by_id[chunk_id].chapter_id,
            start_page=chunk_by_id[chunk_id].start_page,
            end_page=chunk_by_id[chunk_id].end_page,
            rrf_score=rrf_scores[chunk_id],
            rerank_score=rerank_score,
        )
        for chunk_id, rerank_score in reranked
    ]
