# upload PDF, list documents/chapters

import uuid
from pathlib import Path

import fitz
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile

from app.core.ingestion import process_document
from app.db.models import Chapter, Conversation, Document
from app.db.session import SessionLocal
from app.schemas.chat import ConversationOut
from app.schemas.document import (
    ChapterOut,
    DocumentListItem,
    DocumentStatusResponse,
    DocumentUploadResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
DOCUMENTS_DIR = Path(__file__).resolve().parents[3] / "data" / "documents"


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(file: UploadFile = File(...), *, background_tasks: BackgroundTasks):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    content = await file.read()
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds the 50 MB upload limit")

    document_id = str(uuid.uuid4())
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DOCUMENTS_DIR / f"{document_id}.pdf"
    file_path.write_bytes(content)

    # Prettify a raw filename stem ("some_report-v2") into readable title case
    # ("Some Report V2") for display; the underlying stem often has none.
    title = Path(file.filename).stem.replace("_", " ").replace("-", " ").strip().title()
    session = SessionLocal()
    try:
        document = Document(
            id=document_id,
            title=title,
            status="processing",
            file_path=str(file_path),
        )
        session.add(document)
        session.commit()
    finally:
        session.close()

    background_tasks.add_task(process_document, document_id)

    return DocumentUploadResponse(id=document_id, title=title, status="processing")


@router.get("", response_model=list[DocumentListItem])
def list_documents():
    session = SessionLocal()
    try:
        documents = session.query(Document).order_by(Document.uploaded_at.desc()).all()
        results = []
        for document in documents:
            conversation = (
                session.query(Conversation)
                .filter_by(document_id=document.id)
                .order_by(Conversation.created_at.asc())
                .first()
            )
            results.append(
                DocumentListItem(
                    id=document.id,
                    title=document.title,
                    author=document.author,
                    total_pages=document.total_pages,
                    status=document.status,
                    current_page=conversation.current_page if conversation else None,
                    conversation_id=conversation.id if conversation else None,
                )
            )
        return results
    finally:
        session.close()


@router.get("/{document_id}", response_model=DocumentStatusResponse)
def get_document(document_id: str):
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return DocumentStatusResponse(
            id=document.id,
            title=document.title,
            author=document.author,
            status=document.status,
            total_pages=document.total_pages,
            error_message=document.error_message,
        )
    finally:
        session.close()


@router.get("/{document_id}/chapters", response_model=list[ChapterOut])
def list_chapters(document_id: str):
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        chapters = (
            session.query(Chapter)
            .filter_by(document_id=document_id)
            .order_by(Chapter.chapter_number)
            .all()
        )
        return [
            ChapterOut(
                id=chapter.id,
                chapter_number=chapter.chapter_number,
                title=chapter.title,
                start_page=chapter.start_page,
                end_page=chapter.end_page,
            )
            for chapter in chapters
        ]
    finally:
        session.close()


@router.get("/{document_id}/pages/{page_number}")
def get_document_page_image(document_id: str, page_number: int):
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        file_path = document.file_path
        total_pages = document.total_pages
    finally:
        session.close()

    if not file_path or not total_pages:
        raise HTTPException(status_code=404, detail="Document has no rendered pages yet")
    if not (1 <= page_number <= total_pages):
        raise HTTPException(status_code=404, detail="Page number out of range")

    pdf = fitz.open(file_path)
    try:
        page = pdf[page_number - 1]
        png_bytes = page.get_pixmap(dpi=150).tobytes("png")
    finally:
        pdf.close()

    return Response(content=png_bytes, media_type="image/png")


@router.get("/{document_id}/conversation", response_model=ConversationOut)
def get_or_create_conversation(document_id: str):
    """Each document maps to exactly one conversation -- returns the existing
    one if present, otherwise creates it. Keeps 'open this book' idempotent
    on the frontend without a separate create-vs-fetch branch."""
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        conversation = (
            session.query(Conversation)
            .filter_by(document_id=document_id)
            .order_by(Conversation.created_at.asc())
            .first()
        )
        if conversation is None:
            conversation = Conversation(
                id=str(uuid.uuid4()),
                document_id=document_id,
                title=document.title,
            )
            session.add(conversation)
            session.commit()

        return ConversationOut(
            id=conversation.id,
            document_id=conversation.document_id,
            title=conversation.title,
            answer_tone=conversation.answer_tone,
            current_page=conversation.current_page,
        )
    finally:
        session.close()
