"""Manual sanity check: embed a test question and print the top similarity
matches from Chroma, so relevance can be eyeballed by a human.

Usage:
    ./venv/bin/python scripts/similarity_search.py "What is multi-head attention?"
    ./venv/bin/python scripts/similarity_search.py "..." --top-k 8 --document-id <id>
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.embeddings import embed_texts  # noqa: E402
from app.core.vector_store import query_similar  # noqa: E402
from app.db.models import Chapter  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Test question to embed and search for")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--document-id", default=None, help="Restrict search to one document")
    args = parser.parse_args()

    [embedding] = embed_texts([args.question])
    where = {"document_id": args.document_id} if args.document_id else None
    results = query_similar(embedding, top_k=args.top_k, where=where)

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    print(f"Query: {args.question!r}\n")
    if not ids:
        print("No matches found.")
        return

    session = SessionLocal()
    try:
        for rank, (chunk_id, text, metadata, distance) in enumerate(
            zip(ids, documents, metadatas, distances), start=1
        ):
            chapter = session.get(Chapter, metadata.get("chapter_id"))
            chapter_label = chapter.title if chapter else metadata.get("chapter_id")
            snippet = " ".join(text.split())[:300]
            print(f"#{rank}  distance={distance:.4f}  chunk_id={chunk_id}")
            print(
                f"      chapter: {chapter_label}   "
                f"pages {metadata.get('start_page')}-{metadata.get('end_page')}   "
                f"document_id={metadata.get('document_id')}"
            )
            print(f'      "{snippet}..."')
            print()
    finally:
        session.close()


if __name__ == "__main__":
    main()
