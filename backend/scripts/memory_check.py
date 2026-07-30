"""Manual sanity check for the conversation-memory mechanism: runs a sequence
of /chat turns against a running app (enough to trigger a summary rollover,
since SHORT_TERM_WINDOW=8 messages = 4 Q&A pairs), then prints the resulting
conversation state so it can be eyeballed.

What this is checking for:
  - turn 5 ("How does that compare...") is a pronoun follow-up to turns 3/4
    (BLEU scores) -- tests query condensation resolving "that".
  - by turn 10, the BLEU-score turns (3/4) have fallen out of the raw
    SHORT_TERM_WINDOW and should only be reachable via the rolling summary --
    tests that the fold-into-summary step actually preserved that fact.

Usage:
    ./venv/bin/python scripts/memory_check.py [--document-id ID]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.db.models import Conversation, Document  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_QUESTIONS = [
    "What is the main architecture proposed in this paper?",
    "What tasks were used to evaluate the model?",
    "What BLEU score did the model achieve on the English-to-German translation task?",
    "What BLEU score did it get on English-to-French?",
    "How does that compare to the previous best results?",
    "What is self-attention?",
    "How many layers does the encoder have in the base model?",
    "What optimizer was used to train the model?",
    "What regularization techniques did they use during training?",
    "Going back to what we discussed about BLEU scores earlier, which task scored higher?",
]


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", default=None)
    args = parser.parse_args()

    init_db()
    document_id = args.document_id or _find_document_id("attention_is_all_you_need")

    client = TestClient(app)
    response = client.post("/conversations", json={"document_id": document_id})
    response.raise_for_status()
    conversation_id = response.json()["id"]
    print(f"conversation_id: {conversation_id}\n")

    for i, question in enumerate(TEST_QUESTIONS, start=1):
        response = client.post(
            "/chat", json={"conversation_id": conversation_id, "question": question}
        )
        response.raise_for_status()
        body = response.json()
        print(f"--- turn {i} ---")
        print(f"Q: {question}")
        print(f"A: {body['answer']}")
        print(f"is_refusal={body['is_refusal']}  top_rerank_score={body['top_rerank_score']}")
        for src in body["sources"]:
            print(f"  source: {src['chapter_title']}  pages {src['start_page']}-{src['end_page']}")
        print()

    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        message_count = len(conversation.messages)
        print("=" * 80)
        print(f"Total messages stored: {message_count}")
        print(f"summarized_message_count: {conversation.summarized_message_count}")
        print(f"Rolling summary:\n{conversation.summary}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
