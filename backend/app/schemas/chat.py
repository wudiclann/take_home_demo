# Pydantic request/response models for chat/messages

from datetime import datetime

from pydantic import BaseModel


class ConversationCreateRequest(BaseModel):
    document_id: str
    answer_tone: str = "conversational"


class ConversationOut(BaseModel):
    id: str
    document_id: str
    title: str | None
    answer_tone: str
    current_page: int | None


class ConversationUpdateRequest(BaseModel):
    current_page: int | None = None
    answer_tone: str | None = None
    title: str | None = None


class ChatRequest(BaseModel):
    conversation_id: str
    question: str


class SourceOut(BaseModel):
    chapter_title: str | None
    start_page: int | None
    end_page: int | None


class ChatResponse(BaseModel):
    message_id: str
    answer: str
    is_refusal: bool
    top_rerank_score: float | None
    sources: list[SourceOut]


class TranscribeResponse(BaseModel):
    text: str


class AskResponse(BaseModel):
    message_id: str
    question: str  # the transcribed question, so the frontend can show what was heard
    answer: str
    is_refusal: bool
    top_rerank_score: float | None
    sources: list[SourceOut]
    audio_path: str


class MessageOut(BaseModel):
    id: str
    role: str
    text: str
    audio_path: str | None
    audio_duration_s: float | None
    top_rerank_score: float | None
    is_refusal: bool | None
    created_at: datetime
    sources: list[SourceOut]
