# Conversation + chat endpoints: create/update/delete conversations, list a
# conversation's message history, and the two ways to ask a question -- text
# (/chat) and voice (/ask, which also runs ASR first). Both answer paths share
# helpers below so the two endpoints can't drift out of sync with each other.
#
# 对话与聊天相关接口：创建/更新/删除对话、获取对话的消息历史，
# 以及两种提问方式——纯文本（/chat）和语音（/ask，会先做语音识别）。
# 两条路径共用下面的辅助函数，避免两个接口的逻辑逐渐产生偏差。

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile

from app.core.api_key import is_configured
from app.core.asr import transcribe_audio
from app.core.memory import load_memory, update_summary_if_needed
from app.core.rag import AnswerResult, generate_answer
from app.core.rate_limit import limiter
from app.core.tts import delete_audio_file, save_raw_audio, synthesize_speech
from app.db.models import Chapter, Conversation, Document, Message, MessageSource
from app.db.session import SessionLocal
from app.schemas.chat import (
    AskResponse,
    ChatRequest,
    ChatResponse,
    ConversationCreateRequest,
    ConversationOut,
    ConversationUpdateRequest,
    MessageOut,
    SourceOut,
    TranscribeResponse,
)

router = APIRouter(tags=["chat"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # OpenAI Whisper API's own file size limit / OpenAI Whisper API 自身的文件大小上限


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


def _load_conversation_context(conversation_id: str) -> tuple[str, str]:
    """Returns (document_id, answer_tone), raising 404 if the conversation doesn't exist.
    返回 (document_id, answer_tone)；如果对话不存在则抛出 404 错误。"""
    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation.document_id, conversation.answer_tone
    finally:
        session.close()


def _generate_answer_with_audio(
    document_id: str, question: str, memory, answer_tone: str
) -> tuple[AnswerResult, str, str]:
    """generate_answer() + synthesize the answer to speech. Every answer gets audio --
    text and voice input both end up speaking back to the user, including refusals and
    small talk. Returns (result, assistant_message_id, audio_url).

    调用 generate_answer() 生成回答，并把回答合成为语音。无论文本还是语音
    输入，最终都会以语音回复用户——包括拒答和闲聊回复也不例外。
    返回 (result, assistant_message_id, audio_url)。
    """
    result = generate_answer(document_id, question, memory, answer_tone)
    assistant_message_id = str(uuid.uuid4())
    synthesize_speech(result.answer, assistant_message_id)
    audio_url = f"/audio/{assistant_message_id}.mp3"  # servable via the static mount, not a filesystem path / 通过静态文件挂载对外访问的 URL，不是本地文件路径
    return result, assistant_message_id, audio_url


def _persist_turn(
    conversation_id: str,
    question: str,
    result: AnswerResult,
    assistant_message_id: str | None = None,
    audio_path: str | None = None,
    user_message_id: str | None = None,
    user_audio_path: str | None = None,
) -> tuple[str, list[SourceOut]]:
    """Saves the user question + assistant answer (+ its sources) as a turn.
    Returns (assistant_message_id, sources_out).

    将用户的提问与助手的回答（及其引用来源）作为一轮对话保存下来。
    返回 (assistant_message_id, sources_out)。
    """
    assistant_message_id = assistant_message_id or str(uuid.uuid4())
    user_message_id = user_message_id or str(uuid.uuid4())
    session = SessionLocal()
    try:
        user_message = Message(
            id=user_message_id,
            conversation_id=conversation_id,
            role="user",
            text=question,
            audio_path=user_audio_path,
        )
        assistant_message = Message(
            id=assistant_message_id,
            conversation_id=conversation_id,
            role="assistant",
            text=result.answer,
            audio_path=audio_path,
            top_rerank_score=result.top_rerank_score,
            is_refusal=result.is_refusal,
        )
        session.add(user_message)
        session.add(assistant_message)
        session.flush()  # populate assistant_message.id for the sources below / 填充 assistant_message.id，供下面创建来源记录使用

        sources_out: list[SourceOut] = []
        for chunk in result.sources:
            chapter = session.get(Chapter, chunk.chapter_id) if chunk.chapter_id else None
            session.add(
                MessageSource(
                    id=str(uuid.uuid4()),
                    message_id=assistant_message.id,
                    chapter_id=chunk.chapter_id,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                    chunk_id=chunk.chunk_id,
                )
            )
            sources_out.append(
                SourceOut(
                    chapter_title=chapter.title if chapter else None,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                )
            )

        session.commit()
        return assistant_message.id, sources_out
    finally:
        session.close()


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)):
    """Transcribes an audio clip to text on its own -- used internally by
    /ask, and directly testable/usable standalone.
    独立地将一段音频转录为文字——供 /ask 内部调用，
    也可以单独直接测试或使用。"""
    _require_openai_key()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file exceeds the 25 MB Whisper API limit")

    text = transcribe_audio(content, filename=file.filename or "audio.webm")
    return TranscribeResponse(text=text)


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationCreateRequest):
    """Always creates a new conversation for a document (unlike
    GET /documents/{id}/conversation, which is get-or-create) -- kept around
    mainly so tests can spin up a fresh, isolated conversation on demand.
    总是为文档新建一个对话（不同于 GET /documents/{id}/conversation 的
    "获取或创建"语义）——保留这个接口主要是方便测试按需创建全新的、
    互相隔离的对话。"""
    session = SessionLocal()
    try:
        document = session.get(Document, payload.document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        conversation = Conversation(
            id=str(uuid.uuid4()),
            document_id=document.id,
            title=document.title,
            answer_tone=payload.answer_tone,
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


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def update_conversation(conversation_id: str, payload: ConversationUpdateRequest):
    """Partially updates a conversation -- reading position, answer tone,
    and/or title, whichever fields were provided.
    对对话做部分更新——阅读进度、回答语气和/或标题，只更新传入的字段。"""
    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if payload.current_page is not None:
            conversation.current_page = payload.current_page
        if payload.answer_tone is not None:
            conversation.answer_tone = payload.answer_tone
        if payload.title is not None:
            conversation.title = payload.title
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


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, background_tasks: BackgroundTasks):
    """Deletes a conversation (cascading to its messages/sources in SQLite),
    then cleans up every message's audio file on disk in the background.
    删除一个对话（SQLite 会级联删除其消息和来源），
    然后在后台清理该对话下每条消息对应的音频文件。"""
    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        audio_paths = [m.audio_path for m in conversation.messages if m.audio_path]
        session.delete(conversation)  # cascades to messages/message_sources / 级联删除消息与消息来源
        session.commit()
    finally:
        session.close()

    # File cleanup runs after the response is sent -- it scales with message count
    # (one disk delete per audio file), which made long conversations noticeably slow
    # to delete when this ran synchronously in the request path.
    # 文件清理在响应发送之后进行——耗时随消息数量增长（每个音频文件一次磁盘
    # 删除操作），如果放在请求处理过程中同步执行，长对话的删除会明显变慢。
    for audio_path in audio_paths:
        background_tasks.add_task(delete_audio_file, audio_path)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: str):
    """Returns a conversation's full message history in chronological order,
    each with its citations -- used to render the chat thread.
    按时间顺序返回一个对话的完整消息历史，每条消息附带其引用来源——
    用于渲染聊天记录界面。"""
    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        messages = (
            session.query(Message)
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

        results = []
        for message in messages:
            sources_out = []
            for source in message.sources:
                chapter = session.get(Chapter, source.chapter_id) if source.chapter_id else None
                sources_out.append(
                    SourceOut(
                        chapter_title=chapter.title if chapter else None,
                        start_page=source.start_page,
                        end_page=source.end_page,
                    )
                )
            results.append(
                MessageOut(
                    id=message.id,
                    role=message.role,
                    text=message.text,
                    audio_path=message.audio_path,
                    audio_duration_s=message.audio_duration_s,
                    top_rerank_score=message.top_rerank_score,
                    is_refusal=message.is_refusal,
                    created_at=message.created_at,
                    sources=sources_out,
                )
            )
        return results
    finally:
        session.close()


@router.post("/chat", response_model=ChatResponse, status_code=201)
@limiter.limit("20/minute")
def chat(request: Request, payload: ChatRequest, background_tasks: BackgroundTasks):
    """The text-only question path: load memory, run the RAG pipeline, synthesize
    audio for the answer, persist the turn, and kick off a background memory
    summary update if the short-term window has rolled over.

    纯文本提问路径：加载对话记忆，运行 RAG 流水线，为回答合成语音，
    保存这一轮对话，并在短期记忆窗口发生滚动时，在后台触发摘要更新。
    """
    _require_openai_key()
    document_id, answer_tone = _load_conversation_context(payload.conversation_id)

    memory = load_memory(payload.conversation_id)
    result, assistant_message_id, audio_url = _generate_answer_with_audio(
        document_id, payload.question, memory, answer_tone
    )

    message_id, sources_out = _persist_turn(
        payload.conversation_id,
        payload.question,
        result,
        assistant_message_id=assistant_message_id,
        audio_path=audio_url,
    )

    background_tasks.add_task(update_summary_if_needed, payload.conversation_id)

    return ChatResponse(
        message_id=message_id,
        answer=result.answer,
        is_refusal=result.is_refusal,
        top_rerank_score=result.top_rerank_score,
        sources=sources_out,
        audio_path=audio_url,
    )


@router.post("/ask", response_model=AskResponse, status_code=201)
@limiter.limit("20/minute")
async def ask(
    request: Request,
    background_tasks: BackgroundTasks,
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
):
    """The voice question path: transcribe the recording, save the user's own
    audio for playback, then run the same RAG + TTS + persist flow as /chat.

    语音提问路径：先转录录音，保存用户自己的录音以便回放，
    然后走与 /chat 相同的"检索生成 + 语音合成 + 保存"流程。
    """
    _require_openai_key()
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file exceeds the 25 MB Whisper API limit")

    document_id, answer_tone = _load_conversation_context(conversation_id)

    question = transcribe_audio(content, filename=file.filename or "audio.webm")

    # Save the user's own recording so it can be played back, same as the answer.
    # 保存用户自己的录音，使其和助手的回答一样可以被回放。
    user_message_id = str(uuid.uuid4())
    extension = Path(file.filename).suffix if file.filename else ".webm"
    save_raw_audio(content, user_message_id, extension)
    question_audio_url = f"/audio/{user_message_id}{extension}"

    memory = load_memory(conversation_id)
    result, assistant_message_id, audio_url = _generate_answer_with_audio(
        document_id, question, memory, answer_tone
    )

    message_id, sources_out = _persist_turn(
        conversation_id,
        question,
        result,
        assistant_message_id=assistant_message_id,
        audio_path=audio_url,
        user_message_id=user_message_id,
        user_audio_path=question_audio_url,
    )

    background_tasks.add_task(update_summary_if_needed, conversation_id)

    return AskResponse(
        message_id=message_id,
        question=question,
        question_audio_path=question_audio_url,
        answer=result.answer,
        is_refusal=result.is_refusal,
        top_rerank_score=result.top_rerank_score,
        sources=sources_out,
        audio_path=audio_url,
    )
