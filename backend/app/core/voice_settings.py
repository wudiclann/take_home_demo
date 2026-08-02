# Runtime-mutable TTS voice/speed settings, persisted to .env via the same
# mechanism as the OpenAI API key -- takes effect immediately, no server restart.
#
# 运行时可修改的 TTS 音色/语速设置，通过与 OpenAI API 密钥相同的机制
# 持久化到 .env 文件——修改后立即生效，无需重启服务。

from app.config import get_settings, update_env_var

# All voices gpt-4o-mini-tts currently accepts.
# gpt-4o-mini-tts 当前支持的全部音色。
AVAILABLE_VOICES = [
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
]

# OpenAI's API itself allows 0.25-4.0; narrower here since anything outside this
# is impractical for spoken conversation (too slow to follow / too garbled to understand).
# OpenAI 接口本身支持 0.25-4.0，这里收窄范围，因为超出此范围
# 对语音对话来说并不实用（太慢跟不上，或太快听不清）。
MIN_SPEED = 0.5
MAX_SPEED = 2.0


def is_valid_voice(voice: str) -> bool:
    """Whether `voice` is one of the app's allowed voices.
    `voice` 是否为应用支持的音色之一。"""
    return voice in AVAILABLE_VOICES


def is_valid_speed(speed: float) -> bool:
    """Whether `speed` falls within the app's allowed speed range.
    `speed` 是否落在应用允许的语速范围内。"""
    return MIN_SPEED <= speed <= MAX_SPEED


def get_voice() -> str:
    """Currently configured TTS voice.
    当前配置的 TTS 音色。"""
    return get_settings().tts_voice


def get_speed() -> float:
    """Currently configured TTS speaking speed.
    当前配置的 TTS 语速。"""
    return get_settings().tts_speed


def save_voice(voice: str) -> None:
    """Persists a new TTS voice to .env, effective immediately.
    将新的 TTS 音色保存到 .env，立即生效。"""
    update_env_var("TTS_VOICE", voice)


def save_speed(speed: float) -> None:
    """Persists a new TTS speed to .env, effective immediately.
    将新的 TTS 语速保存到 .env，立即生效。"""
    update_env_var("TTS_SPEED", str(speed))
