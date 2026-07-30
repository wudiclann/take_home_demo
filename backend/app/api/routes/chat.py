# POST audio -> ASR -> RAG -> TTS -> audio response

import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.core.asr import transcribe_audio
from app.core.memory import load_memory, update_summary_if_needed
from app.core.rag import AnswerResult, generate_answer
from app.core.tts import synthesize_speech
from app.db.models import Chapter, Conversation, Document, Message, MessageSource
from app.db.session import SessionLocal
from app.schemas.chat import (
    AskResponse,
    ChatRequest,
    ChatResponse,
    ConversationCreateRequest,
    ConversationOut,
    SourceOut,
    TranscribeResponse,
)

router = APIRouter(tags=["chat"])

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # OpenAI Whisper API's own file size limit


def _load_conversation_context(conversation_id: str) -> tuple[str, str]:
    """Returns (document_id, answer_tone), raising 404 if the conversation doesn't exist."""
    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation.document_id, conversation.answer_tone
    finally:
        session.close()


def _persist_turn(
    conversation_id: str,
    question: str,
    result: AnswerResult,
    assistant_message_id: str | None = None,
    audio_path: str | None = None,
) -> tuple[str, list[SourceOut]]:
    """Saves the user question + assistant answer (+ its sources) as a turn.
    Returns (assistant_message_id, sources_out)."""
    assistant_message_id = assistant_message_id or str(uuid.uuid4())
    session = SessionLocal()
    try:
        user_message = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            text=question,
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
        session.flush()  # populate assistant_message.id for the sources below

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
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file exceeds the 25 MB Whisper API limit")

    text = transcribe_audio(content, filename=file.filename or "audio.webm")
    return TranscribeResponse(text=text)


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationCreateRequest):
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
        )
    finally:
        session.close()


@router.post("/chat", response_model=ChatResponse, status_code=201)
def chat(payload: ChatRequest, background_tasks: BackgroundTasks):
    document_id, answer_tone = _load_conversation_context(payload.conversation_id)

    memory = load_memory(payload.conversation_id)
    result = generate_answer(document_id, payload.question, memory, answer_tone)

    message_id, sources_out = _persist_turn(payload.conversation_id, payload.question, result)

    background_tasks.add_task(update_summary_if_needed, payload.conversation_id)

    return ChatResponse(
        message_id=message_id,
        answer=result.answer,
        is_refusal=result.is_refusal,
        top_rerank_score=result.top_rerank_score,
        sources=sources_out,
    )


@router.post("/ask", response_model=AskResponse, status_code=201)
async def ask(
    background_tasks: BackgroundTasks,
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file exceeds the 25 MB Whisper API limit")

    document_id, answer_tone = _load_conversation_context(conversation_id)

    question = transcribe_audio(content, filename=file.filename or "audio.webm")

    memory = load_memory(conversation_id)
    result = generate_answer(document_id, question, memory, answer_tone)

    assistant_message_id = str(uuid.uuid4())
    audio_path = str(synthesize_speech(result.answer, assistant_message_id))

    message_id, sources_out = _persist_turn(
        conversation_id,
        question,
        result,
        assistant_message_id=assistant_message_id,
        audio_path=audio_path,
    )

    background_tasks.add_task(update_summary_if_needed, conversation_id)

    return AskResponse(
        message_id=message_id,
        question=question,
        answer=result.answer,
        is_refusal=result.is_refusal,
        top_rerank_score=result.top_rerank_score,
        sources=sources_out,
        audio_path=audio_path,
    )
