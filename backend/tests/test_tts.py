"""Real (no-mock) test for TTS synthesis: hits the real OpenAI TTS API."""

import uuid


def test_synthesize_speech_creates_valid_audio_file(isolated_app_storage):
    from app.core.tts import synthesize_speech

    message_id = str(uuid.uuid4())
    path = synthesize_speech("This is a short test sentence for text to speech.", message_id)

    assert path.exists()
    assert path.name == f"{message_id}.mp3"

    content = path.read_bytes()
    assert len(content) > 1000  # a real few-second clip, not an empty/error stub
    # MP3 files start with either an ID3 tag or an MPEG frame sync (0xFFEx/0xFFFx).
    assert content[:3] == b"ID3" or (content[0] == 0xFF and (content[1] & 0xE0) == 0xE0)
