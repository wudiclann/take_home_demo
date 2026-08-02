"""End-to-end QA benchmark: hits /chat with a fixed set of real questions about the
book (backed by scripts/qa_benchmark.json) and checks each answer for expected
keyword coverage -- or, for the one deliberately out-of-scope case, that the
refusal gate correctly fired instead of guessing. Reports a per-case PASS/FAIL
and a summary count.

This is the "does the whole answer-generation pipeline actually produce correct,
grounded answers" check -- complementary to eval_retrieval.py (retrieval quality
in isolation, no answer generation) and the pytest suite (endpoint-level
correctness: status codes, persistence, audio, gating -- not answer content).

Each case runs in its own fresh conversation, so cases are independent of each
other (no cross-case memory contamination).

Usage:
    ./venv/bin/python scripts/run_qa_benchmark.py [--document-id ID] [--cases FILE]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.db.models import Document  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402

DEFAULT_CASES_FILE = Path(__file__).resolve().parent / "qa_benchmark.json"


def _normalize_title(title: str) -> str:
    return title.lower().replace("_", " ").replace("-", " ").strip()


def _find_document_id(title_hint: str) -> str:
    target = _normalize_title(title_hint)
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
    raise SystemExit(f"No ready document matching {target!r} found -- ingest it first.")


def run_case(client: TestClient, document_id: str, case: dict) -> tuple[bool, str]:
    conversation_id = client.post(
        "/conversations", json={"document_id": document_id}
    ).json()["id"]

    response = client.post(
        "/chat", json={"conversation_id": conversation_id, "question": case["question"]}
    )
    response.raise_for_status()
    body = response.json()

    if case.get("expect_refusal"):
        passed = body["is_refusal"] is True
        detail = "correctly refused" if passed else "did NOT refuse (expected it to)"
        return passed, f"{detail} -- answer: {body['answer']!r}"

    if body["is_refusal"]:
        return False, f"refused unexpectedly -- answer: {body['answer']!r}"

    answer_lower = body["answer"].lower()
    missing = [kw for kw in case["keywords"] if kw.lower() not in answer_lower]
    passed = not missing
    detail = "all keywords found" if passed else f"missing keywords: {missing}"
    return passed, f"{detail} -- answer: {body['answer']!r}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_FILE)
    args = parser.parse_args()

    init_db()
    document_id = args.document_id or _find_document_id("attention_is_all_you_need")
    cases = json.loads(args.cases.read_text())

    client = TestClient(app)

    results = []
    for case in cases:
        passed, detail = run_case(client, document_id, case)
        results.append(passed)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {case['id']}: {case['question']}")
        print(f"       {detail}\n")

    passed_count = sum(results)
    print("=" * 80)
    print(f"{passed_count}/{len(results)} cases passed")
    if passed_count < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
