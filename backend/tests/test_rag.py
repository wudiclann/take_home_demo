"""Real (no-mock) tests for app.core.rag:
- analyze_query(): the merged, memory-aware classify+condense call.
- generate_refusal(): the LLM-generated refusal wording, now memory-aware too.

Both gaps being tested here are about the same failure mode: a short follow-up
like "why not?" only makes sense given the prior turn, so both functions need
conversation memory to handle it correctly.
"""

EMPTY_MEMORY_KWARGS = {"summary": None, "recent_messages": []}


def _memory_with_turns(*turns: tuple[str, str]):
    """Builds a transient (unpersisted) ConversationMemory from (role, text) pairs,
    for tests that need real memory content without going through the DB."""
    from app.core.memory import ConversationMemory
    from app.db.models import Message

    return ConversationMemory(
        summary=None, recent_messages=[Message(role=role, text=text) for role, text in turns]
    )


def test_generate_refusal_produces_natural_varied_text():
    from app.core.memory import ConversationMemory
    from app.core.rag import REFUSAL_FALLBACK_MESSAGE, generate_refusal

    memory = ConversationMemory(**EMPTY_MEMORY_KWARGS)
    first = generate_refusal(
        "Does the paper report any results on ImageNet image classification?",
        "conversational",
        memory,
    )
    second = generate_refusal(
        "What was the stock price of Google in 2017?", "conversational", memory
    )

    for answer in (first, second):
        assert answer.strip()
        # Confirms the LLM path actually ran rather than silently falling back --
        # the fallback constant is only supposed to appear if the API call itself errors.
        assert answer != REFUSAL_FALLBACK_MESSAGE
    # Two different out-of-scope questions shouldn't produce the exact same
    # canned sentence -- that would mean it's not really LLM-generated wording.
    assert first != second


def test_generate_refusal_does_not_answer_from_outside_knowledge():
    from app.core.memory import ConversationMemory
    from app.core.rag import generate_refusal

    memory = ConversationMemory(**EMPTY_MEMORY_KWARGS)
    answer = generate_refusal(
        "What was the stock price of Google in 2017?", "conversational", memory
    )
    # A correct refusal should not contain an actual stock-price-shaped answer.
    assert "$" not in answer


def test_generate_refusal_uses_memory_to_stay_grounded_in_prior_topic():
    from app.core.rag import generate_refusal

    memory = _memory_with_turns(
        ("user", "What was the stock price of Google in 2017?"),
        (
            "assistant",
            "I couldn't find anything about Google's stock price in this book. "
            "It only covers a neural network architecture paper.",
        ),
    )
    answer = generate_refusal("why not?", "conversational", memory)
    # A follow-up refusal should reference the actual prior topic, not be a
    # generic non-answer with no idea what "why not" refers to.
    assert any(kw in answer.lower() for kw in ["stock", "price", "google", "financial"])


def test_generate_refusal_falls_back_on_api_error(client):
    from app.config import get_settings
    from app.core.memory import ConversationMemory
    from app.core.rag import REFUSAL_FALLBACK_MESSAGE, generate_refusal

    original_key = get_settings().openai_api_key
    try:
        # Format-valid but fake -- passes the /settings validation, then fails for
        # real against the OpenAI API, exercising generate_refusal()'s except branch
        # without mocking anything.
        fake_key = "sk-" + "a" * 40
        assert client.put("/settings/openai-key", json={"api_key": fake_key}).status_code == 200

        memory = ConversationMemory(**EMPTY_MEMORY_KWARGS)
        answer = generate_refusal("Does the book cover ImageNet results?", "conversational", memory)
        assert answer == REFUSAL_FALLBACK_MESSAGE
    finally:
        restore = client.put("/settings/openai-key", json={"api_key": original_key})
        assert restore.status_code == 200
        assert get_settings().openai_api_key == original_key


def test_analyze_query_classifies_greeting_as_conversational():
    from app.core.memory import ConversationMemory
    from app.core.rag import analyze_query

    memory = ConversationMemory(**EMPTY_MEMORY_KWARGS)
    result = analyze_query("Hey, how's it going?", memory)
    assert result.is_conversational is True


def test_analyze_query_classifies_first_turn_question_as_real():
    from app.core.memory import ConversationMemory
    from app.core.rag import analyze_query

    memory = ConversationMemory(**EMPTY_MEMORY_KWARGS)
    result = analyze_query("How many layers does the encoder have?", memory)
    assert result.is_conversational is False
    assert result.search_query.strip()


def test_analyze_query_uses_memory_to_classify_followup_as_real_question():
    from app.core.rag import analyze_query

    # In isolation, "why not?" reads as a throwaway remark. With the prior refusal
    # in context, it's clearly a real continuation of the topic -- this is exactly
    # the gap merging is_conversational + condense_query (with memory) closes.
    memory = _memory_with_turns(
        ("user", "What is the best recipe for chocolate chip cookies?"),
        (
            "assistant",
            "I couldn't find anything about cookie recipes in this book. "
            "It only covers a neural network architecture paper.",
        ),
    )
    result = analyze_query("why not?", memory)
    assert result.is_conversational is False
    assert any(kw in result.search_query.lower() for kw in ["cookie", "recipe", "chocolate"])


def test_multiturn_conversation_then_why_not_followup_stays_grounded(client, sample_document_id):
    """End-to-end scenario: a couple of genuine on-topic turns, then an out-of-scope
    question that refuses, then a bare "why not?" follow-up -- which must still be
    routed as a real question (not misclassified as small talk) and must produce a
    refusal that's actually aware of what it's following up on.

    Uses a cookie-recipe question as the out-of-scope probe rather than something like
    "Google's stock price" -- this fixture PDF's author affiliations literally include
    "Google Research"/"Google Brain", which pulls a stock-price query's rerank score
    close to the refusal threshold for reasons that have nothing to do with the
    classify/condense/refusal logic actually under test here.
    """
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    on_topic_questions = [
        "What is the main architecture proposed in this paper?",
        "How many layers does the encoder have in the base model?",
    ]
    for question in on_topic_questions:
        response = client.post(
            "/chat", json={"conversation_id": conversation_id, "question": question}
        )
        assert response.status_code == 201
        assert response.json()["is_refusal"] is False

    refusal_response = client.post(
        "/chat",
        json={
            "conversation_id": conversation_id,
            "question": "What is the best recipe for chocolate chip cookies?",
        },
    )
    assert refusal_response.status_code == 201
    assert refusal_response.json()["is_refusal"] is True

    followup_response = client.post(
        "/chat", json={"conversation_id": conversation_id, "question": "why not?"}
    )
    assert followup_response.status_code == 201
    body = followup_response.json()
    # The key regression check: a bare "why not?" must still be treated as a real
    # follow-up question (routed through retrieval/refusal), not misclassified as
    # small talk just because it looks like a throwaway remark in isolation.
    assert body["is_refusal"] is True
    answer_lower = body["answer"].lower()
    assert any(kw in answer_lower for kw in ["cookie", "recipe", "chocolate", "baking"])
