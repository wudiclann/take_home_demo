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


def test_synthesize_speech_speed_actually_changes_output(isolated_app_storage):
    """No easy way to assert a voice/speed was actually used from the audio bytes
    alone -- but a higher speed measurably shrinks the file for the same text
    (roughly constant bitrate, shorter duration), so this is a real behavioral
    check that the `speed` param is actually reaching the API call, not just
    silently accepted and ignored."""
    from app.core.tts import synthesize_speech

    text = "This is a somewhat longer sentence, long enough that a speed change should produce a clearly measurable difference in the output file size."
    slow_path = synthesize_speech(text, str(uuid.uuid4()), speed=0.5)
    fast_path = synthesize_speech(text, str(uuid.uuid4()), speed=2.0)

    assert fast_path.stat().st_size < slow_path.stat().st_size


def test_synthesize_speech_defaults_to_settings_voice_and_speed(isolated_app_storage):
    """When voice/speed aren't passed explicitly, synthesize_speech() should use
    whatever's currently saved in Settings, not a hardcoded constant."""
    from app.config import get_settings
    from app.core.tts import synthesize_speech
    from app.core.voice_settings import save_speed, save_voice

    original_voice = get_settings().tts_voice
    original_speed = get_settings().tts_speed
    try:
        save_voice("nova")
        save_speed(0.5)
        slow_default_path = synthesize_speech("Testing default settings.", str(uuid.uuid4()))

        save_speed(2.0)
        fast_default_path = synthesize_speech("Testing default settings.", str(uuid.uuid4()))

        assert fast_default_path.stat().st_size < slow_default_path.stat().st_size
    finally:
        save_voice(original_voice)
        save_speed(original_speed)
