"""Real (no-mock) tests for document listing/detail endpoints: GET /documents,
GET /documents/{id}/chapters, GET /documents/{id}/pages/{n}, and
GET /documents/{id}/conversation (get-or-create).
"""

import time
from pathlib import Path

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "attention_is_all_you_need.pdf"
POLL_ATTEMPTS = 30
POLL_INTERVAL_S = 0.5


def _poll_until_ready(client, document_id: str) -> None:
    for _ in range(POLL_ATTEMPTS):
        response = client.get(f"/documents/{document_id}")
        if response.json()["status"] in ("ready", "failed"):
            assert response.json()["status"] == "ready", response.json().get("error_message")
            return
        time.sleep(POLL_INTERVAL_S)
    raise AssertionError("Document never reached a terminal status")


def test_list_documents_includes_sample(client, sample_document_id):
    response = client.get("/documents")
    assert response.status_code == 200
    matching = [d for d in response.json() if d["id"] == sample_document_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "ready"
    assert matching[0]["total_pages"] == 15


def test_list_chapters_returns_ordered_chapters(client, sample_document_id):
    response = client.get(f"/documents/{sample_document_id}/chapters")
    assert response.status_code == 200
    chapters = response.json()
    assert 5 <= len(chapters) <= 12
    numbers = [c["chapter_number"] for c in chapters]
    assert numbers == sorted(numbers)
    titles = " ".join(c["title"] or "" for c in chapters)
    assert "Introduction" in titles


def test_get_document_page_image_returns_png(client, sample_document_id):
    response = client.get(f"/documents/{sample_document_id}/pages/1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_get_document_page_image_out_of_range(client, sample_document_id):
    response = client.get(f"/documents/{sample_document_id}/pages/9999")
    assert response.status_code == 404


def test_get_or_create_conversation_is_idempotent(client, sample_document_id):
    first = client.get(f"/documents/{sample_document_id}/conversation")
    assert first.status_code == 200
    second = client.get(f"/documents/{sample_document_id}/conversation")
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_delete_document_removes_everything(client):
    with open(FIXTURE_PDF, "rb") as f:
        response = client.post(
            "/documents/upload",
            files={"file": ("attention_is_all_you_need.pdf", f, "application/pdf")},
        )
    document_id = response.json()["id"]
    _poll_until_ready(client, document_id)

    conversation_id = client.get(f"/documents/{document_id}/conversation").json()["id"]
    chat_response = client.post(
        "/chat",
        json={"conversation_id": conversation_id, "question": "What optimizer was used?"},
    )
    audio_path = chat_response.json()["audio_path"]

    from app.core.tts import AUDIO_DIR
    from app.core.vector_store import collection
    from app.db.models import Chapter, Chunk, Conversation, Document, Message
    from app.db.session import SessionLocal

    audio_file = AUDIO_DIR / Path(audio_path).name
    assert audio_file.exists()

    session = SessionLocal()
    try:
        pdf_path = Path(session.get(Document, document_id).file_path)
    finally:
        session.close()
    assert pdf_path.exists()
    assert collection.get(where={"document_id": document_id})["ids"]

    response = client.delete(f"/documents/{document_id}")
    assert response.status_code == 204

    assert client.get(f"/documents/{document_id}").status_code == 404
    assert not audio_file.exists()
    assert not pdf_path.exists()
    assert collection.get(where={"document_id": document_id})["ids"] == []

    session = SessionLocal()
    try:
        assert session.get(Document, document_id) is None
        assert session.query(Chapter).filter_by(document_id=document_id).count() == 0
        assert session.query(Chunk).filter_by(document_id=document_id).count() == 0
        assert session.query(Conversation).filter_by(document_id=document_id).count() == 0
        assert session.query(Message).filter_by(conversation_id=conversation_id).count() == 0
    finally:
        session.close()


def test_delete_document_not_found(client):
    response = client.delete("/documents/does-not-exist")
    assert response.status_code == 404
