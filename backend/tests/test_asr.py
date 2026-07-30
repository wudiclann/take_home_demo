"""Real (no-mock) test for POST /transcribe: hits the real OpenAI Whisper API.

Generates its own sample audio via TTS rather than depending on an external
audio fixture file (none exists in the repo, and TTS is built in the same
step) -- this also doubles as a real round-trip check that the two pipelines
are compatible with each other.
"""

import uuid


def test_transcribe_endpoint_returns_text_from_audio(client, isolated_app_storage):
    from app.core.tts import synthesize_speech

    sentence = "The quick brown fox jumps over the lazy dog."
    path = synthesize_speech(sentence, str(uuid.uuid4()))

    with open(path, "rb") as f:
        response = client.post("/transcribe", files={"file": ("sample.mp3", f, "audio/mpeg")})

    assert response.status_code == 200
    text = response.json()["text"].lower()
    assert "fox" in text
    assert "dog" in text
