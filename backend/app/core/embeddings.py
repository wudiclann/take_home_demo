# OpenAI embeddings client -- turns chunk text into vectors for similarity search.
# OpenAI 向量嵌入客户端——把文本块转换为用于相似度检索的向量。

from openai import OpenAI

from app.config import get_settings

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100  # keeps requests well under OpenAI's per-request input limit for large books
# 让单次请求远低于 OpenAI 单次输入上限，即使是很长的书也没问题

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazily creates (and caches) the OpenAI client, using whatever API key is
    currently configured.
    延迟创建（并缓存）OpenAI 客户端，使用当前配置的 API 密钥。"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def reset_client() -> None:
    """Drops the cached client so the next call picks up a freshly-saved API key.
    清空缓存的客户端，让下一次调用使用刚保存的新 API 密钥。"""
    global _client
    _client = None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds a list of chunk texts into vectors, in batches, preserving input
    order in the output.
    将一批文本块分批转换为向量，输出顺序与输入顺序一致。"""
    if not texts:
        return []
    client = _get_client()
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        embeddings.extend(item.embedding for item in response.data)
    return embeddings
