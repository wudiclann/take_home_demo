# Document endpoints: upload a PDF, list/inspect documents and chapters,
# render page images, delete a document, and get-or-create its conversation.
#
# 文档相关接口：上传 PDF、查看文档与章节列表、渲染页面图片、
# 删除文档，以及获取或创建文档对应的对话。

import os
import uuid
from pathlib import Path

import fitz
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, Response, UploadFile

from app.core.api_key import is_configured
from app.core.ingestion import process_document
from app.core.rate_limit import limiter
from app.core.tts import delete_audio_file
from app.core.vector_store import delete_by_document
from app.db.models import Chapter, Conversation, Document, Message
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
_DEFAULT_DOCUMENTS_DIR = Path(__file__).resolve().parents[3] / "data" / "documents"
# APP_DOCUMENTS_DIR lets tests point at an isolated temp dir instead of the real dev uploads.
# APP_DOCUMENTS_DIR 让测试可以指向一个隔离的临时目录，而不是真实的开发环境上传目录。
DOCUMENTS_DIR = Path(os.environ.get("APP_DOCUMENTS_DIR", _DEFAULT_DOCUMENTS_DIR))


def _require_openai_key() -> None:
    """Raises a 400 if no valid OpenAI key is configured -- called at the top
    of every endpoint that would otherwise call OpenAI.
    如果没有配置有效的 OpenAI 密钥，则抛出 400 错误——
    在每一个会调用 OpenAI 的接口开头调用。"""
    if not is_configured():
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured. Add your key in Settings to continue.",
        )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
@limiter.limit("5/minute")
async def upload_document(request: Request, file: UploadFile = File(...), *, background_tasks: BackgroundTasks):
    """Validates and saves the uploaded PDF, creates its Document row with
    status='processing', and kicks off ingestion (parse/chunk/embed) as a
    background task -- returns immediately rather than making the caller
    wait for the whole pipeline to finish.

    校验并保存上传的 PDF，创建状态为 'processing'（处理中）的文档记录，
    并将摄取流程（解析/分块/向量化）作为后台任务启动——立即返回响应，
    调用方不需要等待整个流水线跑完。
    """
    _require_openai_key()
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
    # 把原始文件名（如 "some_report-v2"）美化成便于展示的标题格式
    # （如 "Some Report V2"）——原始文件名通常没有做过这种格式化。
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
    """Lists every document in the library, newest first, each with its
    reading progress if a conversation exists for it yet.
    列出书库中所有文档，按上传时间从新到旧排序；如果该文档已有对话，
    则一并返回其阅读进度。"""
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
    """Returns one document's current status -- the frontend polls this while
    ingestion runs in the background, until status is 'ready' or 'failed'.
    返回单个文档的当前状态——前端会在后台摄取运行期间轮询这个接口，
    直到状态变为 'ready'（就绪）或 'failed'（失败）。"""
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


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str):
    """Deletes a document and everything that depends on it: the SQLite
    cascade removes chapters/chunks/conversations/messages/message_sources,
    and this handler additionally cleans up the files that live outside the
    database -- the original PDF, every message's audio file, and the
    document's vectors in the vector store.

    删除一个文档及其所有关联数据：SQLite 的级联删除会自动清除章节、
    文本块、对话、消息和消息来源；这个接口还会额外清理数据库之外的文件——
    原始 PDF、每条消息的音频文件，以及向量库中该文档的向量数据。
    """
    session = SessionLocal()
    try:
        document = session.get(Document, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")

        audio_paths = [
            m.audio_path
            for m in session.query(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.document_id == document_id)
            .all()
            if m.audio_path
        ]
        file_path = document.file_path

        session.delete(document)  # cascades to chapters/chunks/conversations/messages/message_sources
        # 级联删除章节/文本块/对话/消息/消息来源
        session.commit()
    finally:
        session.close()

    for audio_path in audio_paths:
        delete_audio_file(audio_path)
    if file_path:
        Path(file_path).unlink(missing_ok=True)
    delete_by_document(document_id)


@router.get("/{document_id}/chapters", response_model=list[ChapterOut])
def list_chapters(document_id: str):
    """Lists a document's chapters in order -- used for the chapter/citation UI.
    按顺序列出一个文档的所有章节——用于章节导航和引用展示。"""
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
    """Renders one PDF page to a PNG image on the fly, for the split-panel
    reading view.
    实时将 PDF 的某一页渲染成 PNG 图片，用于分栏阅读界面展示。"""
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
    on the frontend without a separate create-vs-fetch branch.

    每个文档对应唯一一个对话——如果已存在则直接返回，否则新建一个。
    这样前端"打开这本书"的操作天然幂等，不需要区分"创建"还是"获取"两条分支。
    """
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
