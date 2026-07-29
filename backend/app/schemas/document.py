# Pydantic request/response models for documents/chapters

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: str
    title: str
    status: str


class DocumentStatusResponse(BaseModel):
    id: str
    title: str
    status: str
    total_pages: int | None
    error_message: str | None
