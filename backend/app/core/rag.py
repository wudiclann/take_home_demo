# Orchestrates memory -> query analysis -> retrieval -> LLM call. This is the
# core answer-generation pipeline: given a question, decide whether it's small
# talk or a real question, search the book if needed, decide whether to refuse
# or answer, and generate the final response.
#
# 编排"记忆 -> 查询分析 -> 检索 -> 大模型调用"的核心问答生成流水线：
# 给定一个问题，先判断它是闲聊还是真正的提问，需要时再检索书籍内容，
# 判断该拒答还是正常回答，最终生成回复。

import json
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
#
# 重排序分数低于该阈值时，视为"没有找到相关内容"，转为拒答而不是生成回答。
# 该值为临时值，来自一次小规模评测：明显超出书籍范围的问题得分为 -10.75，
# 而真正可回答的问题得分在 -6.23 至 9.44 之间。待观察更多真实查询后再调整。
REFUSAL_THRESHOLD = -8.0

# Fallback only -- used if the LLM call in generate_refusal() itself fails, so a refusal
# never turns into a hard error just because the "nicer wording" call errored out.
# 仅作为兜底方案——当 generate_refusal() 内部的大模型调用本身失败时使用，
# 这样"生成更自然措辞"这一步出错也不会导致拒答变成一个硬性报错。
REFUSAL_FALLBACK_MESSAGE = (
    "I couldn't find anything in this book that answers that question. "
    "Could you rephrase it, or ask about something covered in the book?"
)

# Per-tone instructions injected into the system prompt, driving conversations.answer_tone.
# 按语气（answer_tone）注入系统提示词的说明文字，对应 conversations.answer_tone 字段。
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
    """The full result of generate_answer(): the answer text, whether it was
    a refusal, the retrieval confidence score, and the source chunks cited.
    generate_answer() 的完整结果：回答文本、是否为拒答、
    检索置信度分数，以及被引用的来源文本块。"""

    answer: str
    is_refusal: bool
    top_rerank_score: float | None
    sources: list[RetrievedChunk]


@dataclass
class QueryAnalysis:
    """The result of analyze_query(): whether the message is small talk, and
    if not, its standalone (context-resolved) search query.
    analyze_query() 的结果：该消息是否为闲聊；如果不是，
    给出已解析上下文引用的独立检索查询语句。"""

    is_conversational: bool
    search_query: str


def analyze_query(question: str, memory: ConversationMemory) -> QueryAnalysis:
    """Single memory-aware LLM call that both classifies the new message (greeting/small
    talk vs. a real question about the book) and, when it's a real question, condenses it
    into a standalone search query with pronouns/references resolved.

    Classification and condensation are merged into one call -- rather than two separate
    calls -- specifically so the classification has the same conversation context the
    condensation needs. A short follow-up like "why not?" is only recognizable as a real
    question (not small talk) given what was just discussed; classifying it from the raw
    text alone misreads it as chit-chat.

    一次结合对话记忆的大模型调用，同时完成两件事：判断新消息是闲聊/问候
    还是关于本书的正式提问；如果是正式提问，则将其改写为一条独立的、
    已解析代词/上下文引用的检索查询语句。

    把"分类"和"改写查询"合并成一次调用（而不是两次独立调用），是为了让
    分类判断也能利用改写查询所需的对话上下文。像"为什么不行？"这样的
    简短追问，只有结合上文才能被正确识别为真正的提问，而不是被误判为闲聊。
    """
    client = OpenAI(api_key=get_settings().openai_api_key)
    memory_context = format_memory_for_prompt(memory)
    prompt = f"""{(memory_context + "\n\n") if memory_context else ""}New message: {question}

Decide whether the new message is small talk (a greeting or casual remark with no real \
connection to the book) or a real question that deserves a substantive answer about the book.

Important: a short reactive phrase like "why not?", "why", "really?", or "what about that?" \
is a REAL QUESTION, never small talk, whenever it follows up on something the assistant just \
said -- even if the assistant's previous message was itself a refusal saying the topic isn't \
covered. The user is asking the assistant to elaborate on that refusal, which needs a real \
(if still refusing) answer, not a chit-chat reply.

Example: previous turns were about "the history of the Eiffel Tower" and the assistant said \
it couldn't find that in the book. New message: "why not?" -> This is a real question. \
is_conversational: false. search_query: "Why doesn't the book cover the history of the \
Eiffel Tower?"

Only mark something conversational if it is truly a greeting/small talk with nothing to \
follow up on (e.g. "hello", "thanks!", "lol ok").

If it is a real question, rewrite it as a standalone search query for retrieving relevant \
passages from the source book, resolving any pronouns or references using the conversation \
context. If it is small talk, leave the search query as an empty string.

Respond with ONLY a JSON object of this exact form, nothing else:
{{"is_conversational": true or false, "search_query": "..."}}"""

    response = client.chat.completions.create(
        model=CONDENSE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(response.choices[0].message.content)
        is_conv = bool(parsed.get("is_conversational"))
        search_query = str(parsed.get("search_query") or "").strip() or question
        return QueryAnalysis(is_conversational=is_conv, search_query=search_query)
    except (json.JSONDecodeError, AttributeError, TypeError):
        # Fail open to "treat as a real question with the raw text as the query" -- the
        # safer default, since misreading a real question as small talk would silently
        # skip retrieval and citations.
        # 出错时"保守失败"：当作真正的提问处理，直接用原始文本作为查询语句——
        # 这是更安全的默认行为，因为把真正的提问误判为闲聊会导致悄悄跳过
        # 检索和引用来源。
        return QueryAnalysis(is_conversational=False, search_query=question)


def generate_refusal(question: str, answer_tone: str, memory: ConversationMemory) -> str:
    """Generates a natural, varied refusal instead of always returning the same fixed
    string. Still does NOT answer from outside/general knowledge -- only the wording of
    the refusal itself is generated, not an actual answer to the question.

    Takes conversation memory (same pattern as generate_answer's main path) so a follow-up
    like "why not?" right after a refusal gets a refusal that's actually aware of what was
    just asked, instead of a generic non-answer with no context.

    生成自然、多样化的拒答话术，而不是每次都返回同一段固定文字。仍然不会
    使用书本以外的通用知识来回答——只有拒答的措辞是由大模型生成的，
    并不是在真正回答这个问题。

    接收对话记忆（与 generate_answer 主流程用法一致），这样在拒答之后
    出现"为什么不行？"这类追问时，新的拒答也能真正了解上文在问什么，
    而不是一句毫无上下文的泛泛之词。
    """
    try:
        client = OpenAI(api_key=get_settings().openai_api_key)
        memory_context = format_memory_for_prompt(memory)
        user_content = (f"{memory_context}\n\n" if memory_context else "") + question
        response = client.chat.completions.create(
            model=ANSWER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful voice assistant for a specific book. The user just "
                        "asked something that isn't covered in this book's content. Let them "
                        "know naturally and briefly that you couldn't find that in the book, "
                        "and invite them to rephrase or ask about something else covered in "
                        "it. Do NOT attempt to answer the question from outside/general "
                        "knowledge -- you only answer based on this book's content. Use the "
                        "conversation context, if any, so your refusal stays grounded in what "
                        "was actually just discussed (e.g. a short follow-up like \"why not?\" "
                        "should reference the specific thing you couldn't find, not be a "
                        "generic non-answer).\n\n"
                        + TONE_SYSTEM_PROMPTS.get(answer_tone, TONE_SYSTEM_PROMPTS["conversational"])
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return REFUSAL_FALLBACK_MESSAGE


def generate_answer(
    document_id: str, question: str, memory: ConversationMemory, answer_tone: str
) -> AnswerResult:
    """The main entry point: routes a question to small talk, a refusal, or a
    grounded answer, and returns the full result either way.
    主入口函数：将一个问题分流到"闲聊回复"、"拒答"或"基于书籍内容的正式回答"
    三条路径之一，并统一返回完整结果。"""
    analysis = analyze_query(question, memory)
    if analysis.is_conversational:
        # Skip retrieval entirely for small talk -- no search, no sources attached.
        # 闲聊消息完全跳过检索——不搜索，也不附带任何引用来源。
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

    retrieved = retrieve(document_id, analysis.search_query, hybrid_k=20, final_k=3)

    top_score = retrieved[0].rerank_score if retrieved else None
    if not retrieved or top_score < REFUSAL_THRESHOLD:
        # Refusal gate: this decision is a hard threshold on the rerank score, not left to
        # LLM judgment -- only the wording of the refusal itself (generate_refusal) is LLM-generated.
        # 拒答判断：这里是对重排序分数的硬性阈值判断，而不是交给大模型自行决定——
        # 只有拒答的具体措辞（generate_refusal）才是由大模型生成的。
        answer = generate_refusal(question, answer_tone, memory)
        return AnswerResult(
            answer=answer, is_refusal=True, top_rerank_score=top_score, sources=[]
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
