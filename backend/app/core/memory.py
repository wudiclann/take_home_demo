# short-term window + rolling summary helper

from dataclasses import dataclass

from openai import OpenAI

from app.config import get_settings
from app.db.models import Conversation, Message
from app.db.session import SessionLocal

SHORT_TERM_WINDOW = 8  # most recent raw message rows kept verbatim in the prompt
SUMMARY_MODEL = "gpt-4o-mini"


@dataclass
class ConversationMemory:
    summary: str | None
    recent_messages: list[Message]  # chronological order, most recent SHORT_TERM_WINDOW rows


def load_memory(conversation_id: str) -> ConversationMemory:
    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        all_messages = (
            session.query(Message)
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )
    finally:
        session.close()
    return ConversationMemory(
        summary=conversation.summary if conversation else None,
        recent_messages=all_messages[-SHORT_TERM_WINDOW:],
    )


def format_memory_for_prompt(memory: ConversationMemory) -> str:
    parts = []
    if memory.summary:
        parts.append(f"Summary of earlier conversation:\n{memory.summary}")
    if memory.recent_messages:
        turns = "\n".join(f"{m.role}: {m.text}" for m in memory.recent_messages)
        parts.append(f"Recent conversation turns:\n{turns}")
    return "\n\n".join(parts)


def update_summary_if_needed(conversation_id: str) -> None:
    """Folds any messages that have fallen out of the short-term window (and
    haven't been summarized yet) into conversations.summary. Meant to run as
    a background task after the response is sent -- must not block /chat."""
    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return
        all_messages = (
            session.query(Message)
            .filter_by(conversation_id=conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        total = len(all_messages)
        should_be_folded = max(0, total - SHORT_TERM_WINDOW)
        already_folded = conversation.summarized_message_count
        to_fold = should_be_folded - already_folded
        if to_fold <= 0:
            return

        new_messages = all_messages[already_folded : already_folded + to_fold]
        turns_text = "\n".join(f"{m.role}: {m.text}" for m in new_messages)

        client = OpenAI(api_key=get_settings().openai_api_key)
        prompt = f"""Update the running summary of this conversation about a book, folding in \
the new turns below. Keep it concise (a few sentences) but preserve important facts, numbers, \
and topics discussed -- the raw turns below will no longer be visible after this.

Existing summary: {conversation.summary or "(none yet)"}

New turns to fold in:
{turns_text}

Updated summary:"""
        response = client.chat.completions.create(
            model=SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        conversation.summary = response.choices[0].message.content.strip()
        conversation.summarized_message_count = already_folded + to_fold
        session.commit()
    finally:
        session.close()
