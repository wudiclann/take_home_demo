# SQLAlchemy models (Document, Chapter, Chunk, Conversation, Message, MessageSource)
# SQLAlchemy 数据模型（文档、章节、文本块、对话、消息、消息来源）

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    """Default id generator for every table's primary key.
    每张表主键的默认 id 生成函数。"""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Default timestamp generator, always UTC.
    默认时间戳生成函数，统一使用 UTC 时间。"""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    """One uploaded book. Owns its chapters, chunks, and conversations --
    deleting a document cascades to all of them.
    一本已上传的书。拥有其章节、文本块和对话——删除文档会级联删除这些数据。"""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String)  # from PDF metadata, when present / 来自 PDF 元数据（如果有）
    total_pages: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, nullable=False)  # 'processing' | 'ready' | 'failed' / 处理中 | 已就绪 | 失败
    error_message: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chapter(Base):
    """One chapter of a document, used for citations and chapter navigation.
    文档中的一个章节，用于生成引用和章节跳转导航。"""

    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    start_page: Mapped[int | None] = mapped_column(Integer)
    end_page: Mapped[int | None] = mapped_column(Integer)

    document: Mapped["Document"] = relationship(back_populates="chapters")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="chapter")


class Chunk(Base):
    """One retrieval-sized piece of a chapter's text. Source of truth for the
    BM25 corpus; the same text + id is also written to the vector store, so
    hybrid search can merge results from both by identity.
    章节文本中大小适合检索的一个片段。是 BM25 语料的权威来源；相同的
    文本和 id 也会写入向量库，使混合检索能按同一 id 合并两边的结果。"""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chapter_id: Mapped[str | None] = mapped_column(ForeignKey("chapters.id"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_page: Mapped[int | None] = mapped_column(Integer)
    end_page: Mapped[int | None] = mapped_column(Integer)

    document: Mapped["Document"] = relationship(back_populates="chunks")
    chapter: Mapped["Chapter | None"] = relationship(back_populates="chunks")


class Conversation(Base):
    """One chat session, always bound to exactly one document. Holds the
    user-facing settings (answer tone, reading position) and both memory
    layers (recent messages live in Message; older ones fold into `summary`).
    一次聊天会话，始终绑定到唯一一本书。保存用户可见的设置（回答语气、
    阅读进度），以及两层对话记忆（最近的消息存在 Message 表中，
    更早的内容会被折叠进 `summary` 字段）。"""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    answer_tone: Mapped[str] = mapped_column(String, default="conversational")
    current_page: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text)
    # Count of the earliest messages (by created_at) already folded into `summary`,
    # so the background summary update only summarizes newly-fallen-out turns.
    # 已经被折叠进 `summary` 的最早消息数量（按创建时间计），
    # 这样后台摘要更新任务每次只需要总结新滑出短期窗口的那部分消息。
    summarized_message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    document: Mapped["Document"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """One turn in a conversation -- either the user's question or the
    assistant's answer. Assistant rows also carry the retrieval confidence
    score and whether the refusal gate fired.
    对话中的一条消息——用户的提问或助手的回答。助手消息还会记录
    检索置信度分数，以及是否触发了拒答判断。"""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # 'user' | 'assistant'
    text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_path: Mapped[str | None] = mapped_column(String)
    audio_duration_s: Mapped[float | None] = mapped_column(Float)
    top_rerank_score: Mapped[float | None] = mapped_column(Float)
    is_refusal: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    sources: Mapped[list["MessageSource"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class MessageSource(Base):
    """One citation attached to an assistant message. A separate table (not
    columns on Message) so one answer can cite multiple non-contiguous page ranges.
    附加在一条助手消息上的一条引用。单独建表（而不是加在 Message 上的
    几个字段），是为了让一个回答可以引用多个不连续的页码范围。"""

    __tablename__ = "message_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), nullable=False)
    chapter_id: Mapped[str | None] = mapped_column(ForeignKey("chapters.id"))
    start_page: Mapped[int | None] = mapped_column(Integer)
    end_page: Mapped[int | None] = mapped_column(Integer)
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("chunks.id"))

    message: Mapped["Message"] = relationship(back_populates="sources")
