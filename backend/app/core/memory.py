# Conversation memory: a short-term window of recent raw messages, plus a
# rolling summary of everything older -- so follow-up questions resolve
# correctly without re-sending the entire conversation history every turn.
#
# 对话记忆模块：短期窗口保留最近的原始消息，更早的内容则折叠进一个
# 滚动更新的摘要——这样追问能够被正确理解，又不需要每一轮都把
# 完整的历史对话发送给模型。

from dataclasses import dataclass

from openai import OpenAI

from app.config import get_settings
from app.db.models import Conversation, Message
from app.db.session import SessionLocal

SHORT_TERM_WINDOW = 8  # most recent raw message rows kept verbatim in the prompt / 提示词中原样保留的最近消息条数
SUMMARY_MODEL = "gpt-4o-mini"


@dataclass
class ConversationMemory:
    """The two memory layers for one conversation: the rolling summary of
    older turns, plus the raw text of the most recent ones.
    一次对话的两层记忆：较早对话的滚动摘要，以及最近若干条消息的原文。"""

    summary: str | None
    recent_messages: list[Message]  # chronological order, most recent SHORT_TERM_WINDOW rows / 按时间顺序排列，最多 SHORT_TERM_WINDOW 条最近消息


def load_memory(conversation_id: str) -> ConversationMemory:
    """Loads both memory layers for a conversation: its rolling summary and
    its last SHORT_TERM_WINDOW messages.
    加载一个对话的两层记忆：滚动摘要，以及最近 SHORT_TERM_WINDOW 条消息。"""
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
    """Renders both memory layers into a plain-text block to prepend to an LLM
    prompt. Returns an empty string if there's no memory yet (first turn).
    将两层记忆渲染成一段纯文本，用于拼接到大模型的提示词前面。
    如果还没有任何记忆（第一轮对话），返回空字符串。"""
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
    a background task after the response is sent -- must not block /chat.

    把已经滑出短期窗口、但还没被摘要过的消息折叠进 conversations.summary。
    设计为在响应发送之后作为后台任务运行——不能阻塞 /chat 的响应。
    """
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
