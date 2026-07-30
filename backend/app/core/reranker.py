# cross-encoder reranking

from sentence_transformers import CrossEncoder

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        _model = CrossEncoder(MODEL_NAME)
    return _model


def rerank(query: str, candidates: list[tuple[str, str]], top_k: int = 3) -> list[tuple[str, float]]:
    """candidates: (chunk_id, text) pairs. Returns top_k (chunk_id, score) sorted descending."""
    if not candidates:
        return []
    pairs = [(query, text) for _, text in candidates]
    scores = _get_model().predict(pairs)
    scored = sorted(zip((cid for cid, _ in candidates), scores), key=lambda pair: pair[1], reverse=True)
    return [(cid, float(score)) for cid, score in scored[:top_k]]
