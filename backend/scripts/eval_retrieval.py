"""Retrieval evaluation: for each case in eval/queries.json, run vector-only
search and the full hybrid (BM25+vector RRF -> cross-encoder rerank) pipeline
side by side, judge each with an LLM, and report a hit-rate comparison.

Two cases are intentionally special, and are still run (not skipped) so the
gap is visible rather than hidden:
  - q12_followup is phrased as a pronoun follow-up ("that"). This script tests
    retrieval in isolation (the raw question text, no query condensation --
    condensation now exists in core/rag.py but is only exercised via /chat),
    so it's expected to underperform here even though /chat handles it
    correctly end-to-end (see scripts/memory_check.py).
  - q14_out_of_scope has no real answer in the document. For this case, a
    "HIT" means the retrieved passages correctly do NOT support an answer
    (the desired signal for the refusal gate in core/rag.py), not that they
    answer it.

Usage:
    ./venv/bin/python scripts/eval_retrieval.py [--document-id ID] [--out eval/results.json]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.embeddings import embed_texts  # noqa: E402
from app.core.retrieval import retrieve  # noqa: E402
from app.core.vector_store import query_similar  # noqa: E402
from app.db.models import Chapter, Document  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

EVAL_FILE = Path(__file__).resolve().parent.parent / "eval" / "queries.json"
JUDGE_MODEL = "gpt-4o-mini"
VECTOR_ONLY_TOP_K = 5


def _normalize_title(title: str) -> str:
    return title.lower().replace("_", " ").replace("-", " ").strip()


def _find_document_id(document_filename: str) -> str:
    target = _normalize_title(Path(document_filename).stem)
    session = SessionLocal()
    try:
        documents = (
            session.query(Document)
            .filter_by(status="ready")
            .order_by(Document.uploaded_at.desc())
            .all()
        )
    finally:
        session.close()
    for document in documents:
        if _normalize_title(document.title) == target:
            return document.id
    raise SystemExit(
        f"No ready document matching {target!r} found -- ingest it first "
        f"(e.g. via POST /documents/upload)."
    )


def _chapter_label(chapter_id: str | None) -> str:
    if chapter_id is None:
        return "?"
    session = SessionLocal()
    try:
        chapter = session.get(Chapter, chapter_id)
    finally:
        session.close()
    return chapter.title if chapter else chapter_id


def _judge(
    question: str,
    expected_answer_summary: str,
    expected_keywords: list[str],
    expect_refusal: bool,
    texts: list[str],
) -> dict:
    client = OpenAI(api_key=get_settings().openai_api_key)
    passages = "\n\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts)) or "(no passages retrieved)"

    if expect_refusal:
        instruction = (
            "This question is deliberately OUT OF SCOPE for the source document. Respond HIT if "
            "the passages correctly do NOT contain a real answer to it (so a downstream system "
            "relying on them would have no basis to answer). Respond MISS if the passages "
            "misleadingly seem to answer it."
        )
    else:
        instruction = (
            "Respond HIT if the passages contain the information needed to produce the expected "
            "answer below. Respond MISS if the necessary information is missing or the passages "
            "are about something else."
        )

    prompt = f"""You are evaluating a document retrieval system for a Q&A app.

Question: {question}
Expected answer: {expected_answer_summary}
Expected keywords: {', '.join(expected_keywords) or '(none)'}

Retrieved passages:
{passages}

{instruction}

Respond with JSON only: {{"verdict": "HIT" or "MISS", "reasoning": "<one sentence>"}}"""

    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", default=None)
    parser.add_argument(
        "--out", default=str(Path(__file__).resolve().parent.parent / "eval" / "results.json")
    )
    args = parser.parse_args()

    eval_data = json.loads(EVAL_FILE.read_text())
    document_id = args.document_id or _find_document_id(eval_data["document"])

    results = []
    vector_hits = 0
    hybrid_hits = 0

    for case in eval_data["cases"]:
        question = case["question"]
        print("=" * 100)
        print(f"[{case['id']}] {question}")
        if case.get("requires_prior_turn"):
            print(f"  NOTE: {case.get('note', '')}")

        [embedding] = embed_texts([question])
        vector_raw = query_similar(embedding, top_k=VECTOR_ONLY_TOP_K, where={"document_id": document_id})
        vector_ids = vector_raw["ids"][0]
        vector_texts = vector_raw["documents"][0]
        vector_distances = vector_raw["distances"][0]

        hybrid_chunks = retrieve(document_id, question, hybrid_k=20, final_k=3)

        print("\n  -- vector-only top 5 --")
        for rank, (chunk_id, text, dist) in enumerate(zip(vector_ids, vector_texts, vector_distances), start=1):
            snippet = " ".join(text.split())[:150]
            print(f"  #{rank} distance={dist:.4f}  \"{snippet}...\"")

        print("\n  -- hybrid (BM25+vector RRF top20) -> reranked top 3 --")
        for rank, rc in enumerate(hybrid_chunks, start=1):
            snippet = " ".join(rc.text.split())[:150]
            print(
                f"  #{rank} rerank_score={rc.rerank_score:.4f} rrf_score={rc.rrf_score:.4f} "
                f"chapter={_chapter_label(rc.chapter_id)} pages={rc.start_page}-{rc.end_page}"
            )
            print(f'       "{snippet}..."')

        vector_verdict = _judge(
            question,
            case["expected_answer_summary"],
            case["expected_keywords"],
            case.get("expect_refusal", False),
            vector_texts,
        )
        hybrid_verdict = _judge(
            question,
            case["expected_answer_summary"],
            case["expected_keywords"],
            case.get("expect_refusal", False),
            [rc.text for rc in hybrid_chunks],
        )

        top_rerank_score = hybrid_chunks[0].rerank_score if hybrid_chunks else None
        print(f"\n  judge: vector-only={vector_verdict['verdict']}  ({vector_verdict['reasoning']})")
        print(f"  judge: hybrid      ={hybrid_verdict['verdict']}  ({hybrid_verdict['reasoning']})")
        print(f"  top rerank score: {top_rerank_score}")

        vector_hits += vector_verdict["verdict"] == "HIT"
        hybrid_hits += hybrid_verdict["verdict"] == "HIT"

        results.append(
            {
                "id": case["id"],
                "question": question,
                "vector_only": {"verdict": vector_verdict, "top_ids": vector_ids},
                "hybrid": {
                    "verdict": hybrid_verdict,
                    "top_chunk_ids": [rc.chunk_id for rc in hybrid_chunks],
                    "top_rerank_score": top_rerank_score,
                },
            }
        )

    total = len(eval_data["cases"])
    print("=" * 100)
    print(f"\nHit-rate  vector-only: {vector_hits}/{total}   hybrid+rerank: {hybrid_hits}/{total}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "document_id": document_id,
                "vector_only_hit_rate": vector_hits / total,
                "hybrid_hit_rate": hybrid_hits / total,
                "cases": results,
            },
            indent=2,
        )
    )
    print(f"\nWrote detailed results to {out_path}")


if __name__ == "__main__":
    main()
