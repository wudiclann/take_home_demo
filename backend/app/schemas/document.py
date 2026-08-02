# Pydantic request/response models for documents/chapters
# 用于文档/章节相关接口的 Pydantic 请求/响应模型

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Response for POST /documents/upload -- ingestion runs in the background,
    so this just confirms the upload was accepted.
    POST /documents/upload 的响应——摄取过程在后台运行，
    这里只是确认上传已被接受。"""

    id: str
    title: str
    status: str


class DocumentStatusResponse(BaseModel):
    """Response for GET /documents/{id} -- used to poll ingestion progress.
    GET /documents/{id} 的响应——用于轮询摄取进度。"""

    id: str
    title: str
    author: str | None
    status: str
    total_pages: int | None
    error_message: str | None


class DocumentListItem(BaseModel):
    """One row in the library grid (GET /documents).
    书库列表中的一本书（GET /documents）。"""

    id: str
    title: str
    author: str | None
    total_pages: int | None
    status: str
    current_page: int | None  # from this document's conversation, if one exists / 来自该文档对应对话的阅读进度（如果存在对话）
    conversation_id: str | None


class ChapterOut(BaseModel):
    """One chapter, used for citations and the chapter list.
    一个章节，用于生成引用和章节列表。"""

    id: str
    chapter_number: int
    title: str | None
    start_page: int | None
    end_page: int | None
