# Whisper API client

from openai import OpenAI

from app.config import get_settings

ASR_MODEL = "whisper-1"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    client = _get_client()
    transcript = client.audio.transcriptions.create(
        model=ASR_MODEL,
        file=(filename, audio_bytes),
        response_format="text",
    )
    return str(transcript).strip()
