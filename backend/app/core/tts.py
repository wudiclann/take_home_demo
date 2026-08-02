# OpenAI TTS API client -- text-to-speech for spoken answers, plus storage
# helpers for both generated answer audio and the user's own recordings.
# OpenAI TTS API 客户端——负责把回答转换成语音，
# 同时提供保存生成音频和用户录音文件的辅助函数。

import os
from pathlib import Path

from openai import OpenAI

from app.config import get_settings

TTS_MODEL = "gpt-4o-mini-tts"

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_AUDIO_DIR = DATA_DIR / "audio"
# APP_AUDIO_DIR lets tests point at an isolated temp dir instead of the real persisted audio.
# APP_AUDIO_DIR 让测试可以指向一个隔离的临时目录，而不是真实持久化的音频目录。
AUDIO_DIR = Path(os.environ.get("APP_AUDIO_DIR", DEFAULT_AUDIO_DIR))

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


def synthesize_speech(
    text: str, message_id: str, voice: str | None = None, speed: float | None = None
) -> Path:
    """Synthesizes `text` to speech and saves it to /data/audio/{message_id}.mp3,
    returning the path it was written to. voice/speed default to the current
    Settings values (user-configurable from the Settings page) when not passed
    explicitly, resolved at call time so a saved change applies immediately.

    将 `text` 合成为语音，保存到 /data/audio/{message_id}.mp3，并返回写入的
    路径。voice/speed 参数如果未显式传入，则默认使用当前 Settings 中的值
    （可在设置页面修改）——这个默认值是在调用时才解析的，因此一旦保存了
    新的设置，会立即在下一次合成时生效。
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_DIR / f"{message_id}.mp3"

    settings = get_settings()
    resolved_voice = voice or settings.tts_voice
    resolved_speed = settings.tts_speed if speed is None else speed

    client = _get_client()
    response = client.audio.speech.create(
        model=TTS_MODEL, voice=resolved_voice, input=text, speed=resolved_speed
    )
    response.write_to_file(output_path)

    return output_path


def save_raw_audio(content: bytes, message_id: str, extension: str = ".webm") -> Path:
    """Saves already-encoded audio bytes (e.g. a user's recorded question) to
    /data/audio/{message_id}{extension}, returning the path it was written to.

    将已经编码好的音频字节（例如用户录制的问题）保存到
    /data/audio/{message_id}{extension}，并返回写入的路径。
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = AUDIO_DIR / f"{message_id}{extension}"
    output_path.write_bytes(content)
    return output_path


def delete_audio_file(audio_url: str) -> None:
    """Deletes a previously-saved audio file given its servable URL (e.g.
    '/audio/{id}.mp3'). Only the filename component is used, so this can't be
    tricked into deleting outside AUDIO_DIR. Safe to call if already missing.

    根据可访问的 URL（例如 '/audio/{id}.mp3'）删除一个此前保存的音频文件。
    只使用其中的文件名部分，因此无法被用来删除 AUDIO_DIR 之外的文件；
    如果文件本来就不存在，调用也是安全的。
    """
    filename = Path(audio_url).name
    (AUDIO_DIR / filename).unlink(missing_ok=True)
