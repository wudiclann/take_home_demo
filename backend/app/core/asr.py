# Whisper API client -- speech-to-text for the voice input path.
# Whisper API 客户端——负责语音输入路径中的语音转文字。

from openai import OpenAI

from app.config import get_settings

ASR_MODEL = "whisper-1"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazily creates (and caches) the OpenAI client, using whatever API key is
    currently configured.
    延迟创建（并缓存）OpenAI 客户端，使用当前配置的 API 密钥。"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def reset_client() -> None:
    """Drops the cached client so the next call picks up a freshly-saved API key.
    清空缓存的客户端，让下一次调用使用刚保存的新 API 密钥。"""
    global _client
    _client = None


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribes a recorded audio clip to text via Whisper.
    通过 Whisper 将一段录音转写为文字。"""
    client = _get_client()
    transcript = client.audio.transcriptions.create(
        model=ASR_MODEL,
        file=(filename, audio_bytes),
        response_format="text",
        # Without this, Whisper's language auto-detection sometimes misidentifies
        # English speech (e.g. as Malay). English-only is already the locked-in
        # scope for v1 (see CLAUDE.md), so forcing it is a bug fix, not new scope.
        # 如果不指定这个参数，Whisper 的自动语言检测有时会把英语误判成
        # 其他语言（例如马来语）。v1 版本本来就锁定只支持英语（见
        # CLAUDE.md），所以强制指定语言是修复 bug，而不是扩大范围。
        language="en",
    )
    return str(transcript).strip()
