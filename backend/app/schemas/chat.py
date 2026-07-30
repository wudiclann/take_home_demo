# Pydantic request/response models for chat/messages

from pydantic import BaseModel


class ConversationCreateRequest(BaseModel):
    document_id: str
    answer_tone: str = "conversational"


class ConversationOut(BaseModel):
    id: str
    document_id: str
    title: str | None
    answer_tone: str


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
