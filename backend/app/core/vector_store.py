# ChromaDB client wrapper -- stores chunk embeddings and runs vector similarity search.
# ChromaDB 客户端封装——存储文本块的向量嵌入，并执行向量相似度检索。

import os
from pathlib import Path

import chromadb

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_CHROMA_DIR = DATA_DIR / "chroma"
# APP_CHROMA_DIR lets tests point at an isolated temp dir instead of the real persisted store.
# APP_CHROMA_DIR 让测试可以指向一个隔离的临时目录，而不是真实持久化的向量库。
CHROMA_DIR = Path(os.environ.get("APP_CHROMA_DIR", DEFAULT_CHROMA_DIR))
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = "chunks"

_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = _client.get_or_create_collection(COLLECTION_NAME)


def add_chunks(
    ids: list[str],
    texts: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict],
) -> None:
    """Writes a batch of chunks (text + embedding + metadata) into the vector
    store, keyed by the same chunk ids used in SQLite -- required so hybrid
    retrieval can merge BM25 and vector results by identity.
    将一批文本块（文本内容 + 向量 + 元数据）写入向量库，使用与 SQLite 中相同的
    chunk id 作为主键——这是混合检索能够按同一 ID 合并 BM25 与向量检索结果的前提。"""
    if not ids:
        return
    collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def query_similar(embedding: list[float], top_k: int = 5, where: dict | None = None):
    """Runs a vector similarity search for the top_k nearest chunks to the
    given embedding, optionally filtered by metadata (e.g. document_id).
    执行向量相似度检索，返回与给定向量最相近的 top_k 个文本块，
    可选按元数据（如 document_id）过滤。"""
    return collection.query(query_embeddings=[embedding], n_results=top_k, where=where)


def delete_by_document(document_id: str) -> None:
    """Removes every chunk belonging to a document -- used when a document is deleted.
    删除某个文档下的所有文本块——在文档被删除时调用。"""
    collection.delete(where={"document_id": document_id})
