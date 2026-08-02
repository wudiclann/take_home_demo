"""Shared pytest fixtures for the whole test session.

`app.db.session` and `app.core.vector_store` each read their storage path from
an env var (APP_DB_PATH / APP_CHROMA_DIR) *once*, at first import, so this
isolation must be set up before any test module imports those modules.
Pytest imports test modules during collection, before any fixture (even an
autouse one) runs -- so every test file must defer its own `from app...`
imports into function/fixture bodies rather than doing them at module top
level, or this fixture's env vars arrive too late to take effect.
"""

import os
import shutil
import uuid
from pathlib import Path

import pytest

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "attention_is_all_you_need.pdf"


@pytest.fixture(scope="session", autouse=True)
def isolated_app_storage(tmp_path_factory):
    """Points the whole test session at a throwaway SQLite DB + Chroma dir
    instead of the real dev database / persisted vector store. Without this,
    every test run would keep appending real (paid) embeddings to the shared
    Chroma directory and rows to the real dev database."""
    tmp_dir = tmp_path_factory.mktemp("app_storage")
    os.environ["APP_DB_PATH"] = str(tmp_dir / "test.db")
    os.environ["APP_CHROMA_DIR"] = str(tmp_dir / "chroma")
    os.environ["APP_AUDIO_DIR"] = str(tmp_dir / "audio")
    os.environ["APP_DOCUMENTS_DIR"] = str(tmp_dir / "documents")

    # Copy the real .env (real API key included) into a throwaway file so
    # settings-mutation tests (PUT /settings/openai-key) never overwrite the
    # developer's actual .env, while real-API tests still have a working key.
    real_env_file = Path(__file__).resolve().parents[1] / ".env"
    tmp_env_file = tmp_dir / ".env"
    shutil.copy(real_env_file, tmp_env_file)
    os.environ["APP_ENV_FILE"] = str(tmp_env_file)

    from app.db.session import init_db

    init_db()


@pytest.fixture(scope="session")
def client(isolated_app_storage):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def sample_document_id(isolated_app_storage, tmp_path_factory):
    """Ingests the sample PDF once for the whole test session (real
    embedding calls) and returns its document_id, reused by every test that
    needs an already-`ready` document rather than re-ingesting per test."""
    from app.core.ingestion import process_document
    from app.db.models import Document
    from app.db.session import SessionLocal

    documents_dir = tmp_path_factory.mktemp("sample_documents")
    document_id = str(uuid.uuid4())
    dest = documents_dir / f"{document_id}.pdf"
    shutil.copy(FIXTURE_PDF, dest)

    session = SessionLocal()
    session.add(
        Document(
            id=document_id,
            title="attention_is_all_you_need",
            status="processing",
            file_path=str(dest),
        )
    )
    session.commit()
    session.close()

    process_document(document_id)

    session = SessionLocal()
    document = session.get(Document, document_id)
    assert document.status == "ready", document.error_message
    session.close()

    return document_id
