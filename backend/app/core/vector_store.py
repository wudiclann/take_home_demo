# ChromaDB client wrapper

import os
from pathlib import Path

import chromadb

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_CHROMA_DIR = DATA_DIR / "chroma"
# APP_CHROMA_DIR lets tests point at an isolated temp dir instead of the real persisted store.
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
    if not ids:
        return
    collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def query_similar(embedding: list[float], top_k: int = 5, where: dict | None = None):
    return collection.query(query_embeddings=[embedding], n_results=top_k, where=where)
