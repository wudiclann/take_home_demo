"""Real (no-mock) test for POST /ask: the full voice pipeline (audio in ->
Whisper transcription -> hybrid retrieval + rerank -> chat completion -> TTS
-> audio out). Uses TTS to generate the input question audio, same approach
as test_asr.py, so no external audio fixture is needed.
"""

import uuid
from pathlib import Path


def test_ask_full_voice_pipeline(client, sample_document_id):
    from app.core.tts import synthesize_speech

    response = client.post("/conversations", json={"document_id": sample_document_id})
    conversation_id = response.json()["id"]

    question_audio_path = synthesize_speech(
        "What BLEU score did the model achieve on the English-to-German translation task?",
        str(uuid.uuid4()),
    )

    with open(question_audio_path, "rb") as f:
        response = client.post(
            "/ask",
            data={"conversation_id": conversation_id},
            files={"file": ("question.mp3", f, "audio/mpeg")},
        )

    assert response.status_code == 201
    body = response.json()

    assert "german" in body["question"].lower()
    assert body["is_refusal"] is False
    assert "28.4" in body["answer"]
    assert body["sources"]

    answer_audio_path = Path(body["audio_path"])
    assert answer_audio_path.exists()
    content = answer_audio_path.read_bytes()
    assert len(content) > 1000
    assert content[:3] == b"ID3" or (content[0] == 0xFF and (content[1] & 0xE0) == 0xE0)

    from app.db.models import Message
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        assistant_message = session.get(Message, body["message_id"])
        assert assistant_message.role == "assistant"
        assert assistant_message.audio_path == body["audio_path"]
    finally:
        session.close()
