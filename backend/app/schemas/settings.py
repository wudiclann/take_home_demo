# Pydantic request/response models for the Settings page (API key, TTS voice/speed)
# 用于设置页面（API 密钥、TTS 音色/语速）相关接口的 Pydantic 请求/响应模型

from pydantic import BaseModel


class SettingsOut(BaseModel):
    """Full current settings state, returned by GET /settings and after every
    settings update -- the raw API key is never included, only whether it's
    configured and its masked display value.
    完整的当前设置状态，由 GET /settings 及每次设置更新后返回——
    真实的 API 密钥永远不会包含在内，只返回是否已配置及其脱敏后的展示值。"""

    is_openai_key_configured: bool
    openai_api_key_masked: str | None
    tts_voice: str
    tts_speed: float
    available_voices: list[str]


class OpenAiKeyUpdateRequest(BaseModel):
    """Body for PUT /settings/openai-key.
    PUT /settings/openai-key 的请求体。"""

    api_key: str


class VoiceSettingsUpdateRequest(BaseModel):
    """Body for PUT /settings/voice.
    PUT /settings/voice 的请求体。"""

    voice: str
    speed: float
