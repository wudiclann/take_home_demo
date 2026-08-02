# Pydantic request/response models for chat/messages
# 用于对话与消息相关接口的 Pydantic 请求/响应模型

from datetime import datetime

from pydantic import BaseModel


class ConversationCreateRequest(BaseModel):
    """Body for POST /conversations.
    POST /conversations 的请求体。"""

    document_id: str
    answer_tone: str = "conversational"


class ConversationOut(BaseModel):
    """A conversation as returned to the frontend.
    返回给前端的对话信息。"""

    id: str
    document_id: str
    title: str | None
    answer_tone: str
    current_page: int | None


class ConversationUpdateRequest(BaseModel):
    """Body for PATCH /conversations/{id} -- every field optional, only the
    ones provided get updated.
    PATCH /conversations/{id} 的请求体——所有字段都是可选的，只更新传入的字段。"""

    current_page: int | None = None
    answer_tone: str | None = None
    title: str | None = None


class ChatRequest(BaseModel):
    """Body for POST /chat -- the text-only question path.
    POST /chat 的请求体——纯文本提问路径。"""

    conversation_id: str
    question: str


class SourceOut(BaseModel):
    """One citation shown under an assistant answer.
    展示在助手回答下方的一条引用来源。"""

    chapter_title: str | None
    start_page: int | None
    end_page: int | None


class ChatResponse(BaseModel):
    """Response for POST /chat.
    POST /chat 的响应。"""

    message_id: str
    answer: str
    is_refusal: bool
    top_rerank_score: float | None
    sources: list[SourceOut]
    audio_path: str


class TranscribeResponse(BaseModel):
    """Response for POST /transcribe.
    POST /transcribe 的响应。"""

    text: str


class AskResponse(ChatResponse):
    """Response for POST /ask -- everything ChatResponse has, plus the
    transcribed question and the user's own recording.
    POST /ask 的响应——包含 ChatResponse 的所有字段，
    另外还有转录出的问题文本和用户自己的录音。"""

    question: str  # the transcribed question, so the frontend can show what was heard / 转录出的问题文本，供前端展示"听到的内容"
    question_audio_path: str  # the user's own recorded question, saved for playback / 用户自己的录音，已保存供回放


class MessageOut(BaseModel):
    """One message row as returned to the frontend (used for conversation history).
    返回给前端的一条消息记录（用于展示对话历史）。"""

    id: str
    role: str
    text: str
    audio_path: str | None
    audio_duration_s: float | None
    top_rerank_score: float | None
    is_refusal: bool | None
    created_at: datetime
    sources: list[SourceOut]
