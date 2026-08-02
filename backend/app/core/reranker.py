# Cross-encoder reranking -- re-scores hybrid search candidates against the
# actual query text for much higher precision than embedding similarity alone.
# 交叉编码器重排序——用实际的查询文本重新给混合检索的候选结果打分，
# 精度远高于只用向量相似度。

from sentence_transformers import CrossEncoder

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

_model: CrossEncoder | None = None


def _get_model() -> CrossEncoder:
    """Lazily loads (and caches) the cross-encoder model.
    延迟加载（并缓存）交叉编码器模型。"""
    global _model
    if _model is None:
        _model = CrossEncoder(MODEL_NAME)
    return _model


def preload_model() -> None:
    """Forces the lazy model load to happen now, rather than on first use --
    called from main.py's startup so the download/load cost doesn't land on
    the first real /chat or /ask request.

    立即触发模型加载，而不是等到第一次真正使用时才加载——在 main.py 启动时
    调用，这样下载/加载模型的耗时就不会转嫁到第一次真实的 /chat 或 /ask 请求上。
    """
    _get_model()


def rerank(query: str, candidates: list[tuple[str, str]], top_k: int = 3) -> list[tuple[str, float]]:
    """candidates: (chunk_id, text) pairs. Returns top_k (chunk_id, score) sorted descending.
    candidates 是 (chunk_id, text) 的列表。返回按分数降序排列的 top_k 个 (chunk_id, score)。"""
    if not candidates:
        return []
    pairs = [(query, text) for _, text in candidates]
    scores = _get_model().predict(pairs)
    scored = sorted(zip((cid for cid, _ in candidates), scores), key=lambda pair: pair[1], reverse=True)
    return [(cid, float(score)) for cid, score in scored[:top_k]]
