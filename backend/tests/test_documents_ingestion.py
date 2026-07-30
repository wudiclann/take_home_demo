import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "attention_is_all_you_need.pdf"
POLL_ATTEMPTS = 30
POLL_INTERVAL_S = 0.5


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolate this test from the real dev database -- session.py reads APP_DB_PATH
    # at import time, so the env var must be set before app modules are imported.
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))

    from fastapi.testclient import TestClient

    from app.db.session import init_db
    from app.main import app

    init_db()
    return TestClient(app)


def _poll_until_terminal(client: "TestClient", document_id: str) -> dict:
    status_body = {}
    for _ in range(POLL_ATTEMPTS):
        response = client.get(f"/documents/{document_id}")
        assert response.status_code == 200
        status_body = response.json()
        if status_body["status"] in ("ready", "failed"):
            return status_body
        time.sleep(POLL_INTERVAL_S)
    raise AssertionError(f"Document never reached a terminal status: {status_body}")


def test_upload_and_ingest_multi_chapter_pdf(client):
    with open(FIXTURE_PDF, "rb") as f:
        response = client.post(
            "/documents/upload",
            files={"file": ("attention_is_all_you_need.pdf", f, "application/pdf")},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processing"
    document_id = body["id"]

    status_body = _poll_until_terminal(client, document_id)
    assert status_body["status"] == "ready", status_body.get("error_message")
    assert status_body["total_pages"] == 15

    from app.db.models import Chapter, Chunk
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        chapters = (
            session.query(Chapter)
            .filter_by(document_id=document_id)
            .order_by(Chapter.chapter_number)
            .all()
        )
        chunks = session.query(Chunk).filter_by(document_id=document_id).all()
    finally:
        session.close()

    # Sane chapter count/metadata: real TOC has 7 top-level sections, plus a
    # front-matter chapter for the title/abstract before "1 Introduction".
    assert 5 <= len(chapters) <= 12
    chapter_ids = {c.id for c in chapters}
    for chapter in chapters:
        assert 1 <= chapter.start_page <= chapter.end_page <= status_body["total_pages"]
    titles = " ".join(c.title or "" for c in chapters)
    assert "Introduction" in titles  # confirms the TOC path matched, not the single-chapter fallback

    # Sane chunk count/metadata: not fixed-size (47 chunks for 15 pages), and every
    # chunk must belong to a real chapter and stay within the document's page range.
    assert 20 <= len(chunks) <= 80
    for chunk in chunks:
        assert chunk.chapter_id in chapter_ids
        assert 1 <= chunk.start_page <= chunk.end_page <= status_body["total_pages"]
        assert chunk.text.strip()
