"""Real (no-mock) tests for POST /conversations and POST /chat, including the
short-term-window + rolling-summary memory mechanism. Hits the real OpenAI
APIs (embeddings, chat completions) and the real cross-encoder model.
"""

from pathlib import Path

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

    # Text input must still come back with audio -- output is always spoken,
    # regardless of whether the question arrived as text or voice.
    assert body["audio_path"].startswith("/audio/")
    audio_response = client.get(body["audio_path"])
    assert audio_response.status_code == 200
    assert len(audio_response.content) > 1000


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

    # Refusals are still spoken back -- a voice-first app shouldn't go silent
    # just because it can't answer.
    assert body["audio_path"].startswith("/audio/")
    audio_response = client.get(body["audio_path"])
    assert audio_response.status_code == 200


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


def test_list_messages_returns_persisted_turn(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    client.post(
        "/chat",
        json={
            "conversation_id": conversation_id,
            "question": "How many layers does the encoder have in the base model?",
        },
    )

    response = client.get(f"/conversations/{conversation_id}/messages")
    assert response.status_code == 200
    messages = response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["sources"]


def test_update_conversation_persists_current_page_and_tone(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    response = client.patch(
        f"/conversations/{conversation_id}",
        json={"current_page": 5, "answer_tone": "scholarly"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["current_page"] == 5
    assert body["answer_tone"] == "scholarly"


def test_delete_conversation_removes_it_and_its_messages(client, sample_document_id):
    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]
    response = client.post(
        "/chat",
        json={"conversation_id": conversation_id, "question": "What optimizer was used?"},
    )
    audio_path = response.json()["audio_path"]

    from app.core.tts import AUDIO_DIR

    audio_file = AUDIO_DIR / Path(audio_path).name
    assert audio_file.exists()

    response = client.delete(f"/conversations/{conversation_id}")
    assert response.status_code == 204

    response = client.get(f"/conversations/{conversation_id}/messages")
    assert response.status_code == 404

    # The answer's audio file on disk must be cleaned up too, not just the DB rows.
    assert not audio_file.exists()
