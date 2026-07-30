# Pydantic request/response models for documents/chapters

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: str
    title: str
    status: str


class DocumentStatusResponse(BaseModel):
    id: str
    title: str
    author: str | None
    status: str
    total_pages: int | None
    error_message: str | None


class DocumentListItem(BaseModel):
    id: str
    title: str
    author: str | None
    total_pages: int | None
    status: str
    current_page: int | None  # from this document's conversation, if one exists
    conversation_id: str | None


class ChapterOut(BaseModel):
    id: str
    chapter_number: int
    title: str | None
    start_page: int | None
    end_page: int | None
