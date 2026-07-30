# OpenAI TTS API client

import os
from pathlib import Path

from openai import OpenAI

from app.config import get_settings

TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_AUDIO_DIR = DATA_DIR / "audio"
# APP_AUDIO_DIR lets tests point at an isolated temp dir instead of the real persisted audio.
AUDIO_DIR = Path(os.environ.get("APP_AUDIO_DIR", DEFAULT_AUDIO_DIR))

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def synthesize_speech(text: str, message_id: str, voice: str = DEFAULT_VOICE) -> Path:
    """Synthesizes `text` to speech and saves it to /data/audio/{message_id}.mp3,
    returning the path it was written to."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_DIR / f"{message_id}.mp3"

    client = _get_client()
    response = client.audio.speech.create(model=TTS_MODEL, voice=voice, input=text)
    response.write_to_file(output_path)

    return output_path
