# orchestrates memory -> query condensation -> retrieval -> LLM call

from dataclasses import dataclass

from openai import OpenAI

from app.config import get_settings
from app.core.memory import ConversationMemory, format_memory_for_prompt
from app.core.retrieval import RetrievedChunk, retrieve

ANSWER_MODEL = "gpt-4o-mini"
CONDENSE_MODEL = "gpt-4o-mini"

# Rerank scores below this are treated as "nothing relevant found" -- refuse rather than
# generate. Provisional: calibrated from one small eval run where a clearly out-of-scope
# question scored -10.75 vs. -6.23..9.44 for genuinely answerable ones. Revisit once more
# real queries have been observed.
REFUSAL_THRESHOLD = -8.0

REFUSAL_MESSAGE = (
    "I couldn't find anything in this book that answers that question. "
    "Could you rephrase it, or ask about something covered in the book?"
)

TONE_SYSTEM_PROMPTS = {
    "concise": (
        "Answer in 1-3 short sentences. Be direct and to the point -- no throat-clearing, "
        "hedging, or elaboration beyond what's asked. Plain, efficient language."
    ),
    "conversational": (
        "Answer in a natural, friendly, conversational tone, as if explaining to a curious "
        "colleague. 2-5 sentences is typical; some elaboration and informal phrasing is fine, "
        "but stay focused on the question."
    ),
    "scholarly": (
        "Answer with academic precision and formal, technical language appropriate for an "
        "expert audience. Give a thorough explanation, note relevant nuance or caveats from "
        "the text, and prefer precise terminology over casual paraphrase."
    ),
}


@dataclass
class AnswerResult:
    answer: str
    is_refusal: bool
    top_rerank_score: float | None
    sources: list[RetrievedChunk]


def condense_query(question: str, memory: ConversationMemory) -> str:
    if not memory.recent_messages and not memory.summary:
        return question  # first turn -- nothing to resolve against, skip the LLM call

    client = OpenAI(api_key=get_settings().openai_api_key)
    prompt = f"""Given the conversation context below and a new question, rewrite the new \
question as a standalone search query for retrieving relevant passages from the source book. \
Resolve any pronouns or references to prior context. Reply with ONLY the rewritten query, \
nothing else.

{format_memory_for_prompt(memory)}

New question: {question}

Standalone search query:"""
    response = client.chat.completions.create(
        model=CONDENSE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def is_conversational(question: str) -> bool:
    """Cheap classifier: True if this is a greeting/small talk, not a real question about
    the book's content. Runs before retrieval so chit-chat never triggers a search or gets
    citations attached."""
    client = OpenAI(api_key=get_settings().openai_api_key)
    prompt = f"""Is the following message a greeting, casual remark, or small talk -- NOT a \
real question about a book's content? Reply with ONLY "yes" or "no".

Message: {question}"""
    response = client.chat.completions.create(
        model=CONDENSE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip().lower().startswith("yes")


def generate_answer(
    document_id: str, question: str, memory: ConversationMemory, answer_tone: str
) -> AnswerResult:
    if is_conversational(question):
        # Skip retrieval entirely for small talk -- no search, no sources attached.
        client = OpenAI(api_key=get_settings().openai_api_key)
        response = client.chat.completions.create(
            model=ANSWER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a friendly voice assistant for a book. Respond "
                    "naturally and briefly to this greeting or casual remark.",
                },
                {"role": "user", "content": question},
            ],
            temperature=0.3,
        )
        answer = response.choices[0].message.content.strip()
        return AnswerResult(answer=answer, is_refusal=False, top_rerank_score=None, sources=[])

    search_query = condense_query(question, memory)
    retrieved = retrieve(document_id, search_query, hybrid_k=20, final_k=3)

    top_score = retrieved[0].rerank_score if retrieved else None
    if not retrieved or top_score < REFUSAL_THRESHOLD:
        return AnswerResult(
            answer=REFUSAL_MESSAGE, is_refusal=True, top_rerank_score=top_score, sources=[]
        )

    passages = "\n\n".join(f"[{i + 1}] {chunk.text}" for i, chunk in enumerate(retrieved))
    system_prompt = (
        "You are a helpful voice assistant for a specific book. If the user sends a greeting, "
        "casual remark, or anything that isn't actually a question about the book, respond "
        "naturally and briefly, like a normal conversational reply -- do not force the book "
        "passages into your answer or treat it as a book question.\n\n"
        "For genuine questions about the book, answer grounded ONLY in the provided passages. "
        "If the passages don't actually contain the answer, say so plainly instead of guessing "
        "or using outside knowledge.\n\n"
        + TONE_SYSTEM_PROMPTS.get(answer_tone, TONE_SYSTEM_PROMPTS["conversational"])
    )
    memory_context = format_memory_for_prompt(memory)
    user_content = (
        (f"{memory_context}\n\n" if memory_context else "")
        + f"Book passages:\n{passages}\n\nQuestion: {question}"
    )

    client = OpenAI(api_key=get_settings().openai_api_key)
    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )
    answer = response.choices[0].message.content.strip()
    return AnswerResult(answer=answer, is_refusal=False, top_rerank_score=top_score, sources=retrieved)