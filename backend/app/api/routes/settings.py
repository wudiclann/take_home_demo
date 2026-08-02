# GET/PUT/DELETE the server-side OpenAI API key (masked on read, format-validated on write)
# and GET/PUT the TTS voice/speed settings.
#
# 设置相关接口：GET/PUT/DELETE 服务器端保存的 OpenAI API 密钥
# （读取时脱敏展示，写入时做格式校验），以及 GET/PUT TTS 音色/语速设置。

from fastapi import APIRouter, HTTPException

from app.core.api_key import clear_key, is_configured, is_valid_format, masked_key, save_key
from app.core.voice_settings import (
    AVAILABLE_VOICES,
    MAX_SPEED,
    MIN_SPEED,
    get_speed,
    get_voice,
    is_valid_speed,
    is_valid_voice,
    save_speed,
    save_voice,
)
from app.schemas.settings import OpenAiKeyUpdateRequest, SettingsOut, VoiceSettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])


def _settings_out() -> SettingsOut:
    """Builds the full current settings snapshot -- shared by every endpoint
    below so they all return a consistent shape after any change.
    构建完整的当前设置快照——下面所有接口共用这个函数，
    确保无论修改了哪一项设置，返回的数据结构都保持一致。"""
    return SettingsOut(
        is_openai_key_configured=is_configured(),
        openai_api_key_masked=masked_key(),
        tts_voice=get_voice(),
        tts_speed=get_speed(),
        available_voices=AVAILABLE_VOICES,
    )


@router.get("", response_model=SettingsOut)
def get_settings_status():
    """Returns the current settings state, for the Settings page to render on load.
    返回当前设置状态，供设置页面在加载时渲染。"""
    return _settings_out()


@router.put("/openai-key", response_model=SettingsOut)
def update_openai_key(payload: OpenAiKeyUpdateRequest):
    """Validates and saves a new OpenAI API key, taking effect immediately.
    校验并保存新的 OpenAI API 密钥，立即生效。"""
    if not is_valid_format(payload.api_key):
        raise HTTPException(status_code=400, detail="That doesn't look like a valid OpenAI API key.")
    save_key(payload.api_key)
    return _settings_out()


@router.delete("/openai-key", response_model=SettingsOut)
def remove_openai_key():
    """Clears the saved OpenAI API key, putting the app back into the
    "not configured" state.
    清除已保存的 OpenAI API 密钥，让应用回到"未配置密钥"的状态。"""
    clear_key()
    return _settings_out()


@router.put("/voice", response_model=SettingsOut)
def update_voice_settings(payload: VoiceSettingsUpdateRequest):
    """Validates and saves a new TTS voice + speaking speed, taking effect immediately.
    校验并保存新的 TTS 音色与语速，立即生效。"""
    if not is_valid_voice(payload.voice):
        raise HTTPException(status_code=400, detail=f"Voice must be one of: {', '.join(AVAILABLE_VOICES)}.")
    if not is_valid_speed(payload.speed):
        raise HTTPException(
            status_code=400, detail=f"Speed must be between {MIN_SPEED} and {MAX_SPEED}."
        )
    save_voice(payload.voice)
    save_speed(payload.speed)
    return _settings_out()
