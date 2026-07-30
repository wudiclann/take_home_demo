"""Real (no-mock) tests for POST /conversations and POST /chat, including the
short-term-window + rolling-summary memory mechanism. Hits the real OpenAI
APIs (embeddings, chat completions) and the real cross-encoder model.
"""

SHORT_TERM_WINDOW = 8  # keep in sync with app.core.memory.SHORT_TERM_WINDOW


def test_create_conversation_defaults(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    assert response.status_code == 201
    body = response.json()
    assert body["document_id"] == sample_document_id
    assert body["answer_tone"] == "conversational"


def test_chat_returns_grounded_answer_with_citations(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    response = client.post(
        "/chat",
        json={
            "conversation_id": conversation_id,
            "question": (
                "What BLEU score did the model achieve on the English-to-German "
                "translation task?"
            ),
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["is_refusal"] is False
    assert "28.4" in body["answer"]
    assert body["sources"]
    for source in body["sources"]:
        assert source["start_page"] is not None


def test_chat_refuses_out_of_scope_question(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    response = client.post(
        "/chat",
        json={
            "conversation_id": conversation_id,
            "question": "Does the paper report any results on ImageNet image classification?",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["is_refusal"] is True
    assert body["sources"] == []


def test_chat_pronoun_followup_resolved_via_condensation(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    first = client.post(
        "/chat",
        json={
            "conversation_id": conversation_id,
            "question": (
                "What BLEU score did the model achieve on the English-to-German "
                "translation task?"
            ),
        },
    )
    assert first.status_code == 201
    assert "28.4" in first.json()["answer"]

    followup = client.post(
        "/chat",
        json={
            "conversation_id": conversation_id,
            "question": "How does that compare to the previous best results?",
        },
    )
    assert followup.status_code == 201
    body = followup.json()
    assert body["is_refusal"] is False
    assert body["sources"]


def test_chat_memory_rollover_folds_old_turns_into_summary(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    # 5 turns = 10 messages, enough to exceed SHORT_TERM_WINDOW=8 and force a fold.
    questions = [
        "What is the main architecture proposed in this paper?",
        "What tasks were used to evaluate the model?",
        "How many layers does the encoder have in the base model?",
        "What optimizer was used to train the model?",
        "What regularization techniques did they use during training?",
    ]
    for question in questions:
        response = client.post(
            "/chat", json={"conversation_id": conversation_id, "question": question}
        )
        assert response.status_code == 201

    from app.db.models import Conversation
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        conversation = session.get(Conversation, conversation_id)
        total_messages = len(conversation.messages)
        assert total_messages == len(questions) * 2
        assert conversation.summarized_message_count == total_messages - SHORT_TERM_WINDOW
        assert conversation.summary
    finally:
        session.close()
