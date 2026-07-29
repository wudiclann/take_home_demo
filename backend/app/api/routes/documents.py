# upload PDF, list documents/chapters

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.core.ingestion import process_document
from app.db.models import Document
from app.db.session import SessionLocal
from app.schemas.document import DocumentStatusResponse, DocumentUploadResponse

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

    title = Path(file.filename).stem
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
            status=document.status,
            total_pages=document.total_pages,
            error_message=document.error_message,
        )
    finally:
        session.close()
