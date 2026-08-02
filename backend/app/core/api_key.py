# Runtime-mutable OpenAI API key: format validation, masking, and persisting
# to the .env file (unlike the rest of Settings, this one field can be changed
# without restarting the server -- see save_key()).
#
# 运行时可修改的 OpenAI API 密钥模块：负责格式校验、脱敏显示，
# 以及持久化到 .env 文件（这个字段可以在不重启服务的情况下修改，
# 详见 save_key()）。

import re

from app.config import get_settings, update_env_var

_KEY_RE = re.compile(r"^sk-[A-Za-z0-9_-]{20,}$")
MASKED_KEY = "sk-************"


def is_valid_format(key: str) -> bool:
    """Format-only check (not a live call to OpenAI) -- must start with 'sk-'
    and be at least 20 characters after that.
    仅做格式校验（不会真正请求 OpenAI 接口）——必须以 'sk-' 开头，
    且之后至少还有 20 个字符。"""
    return bool(_KEY_RE.match(key.strip()))


def is_configured() -> bool:
    """True if a format-valid key is currently saved -- what every
    OpenAI-calling endpoint gates on before doing any work.
    当前是否已保存一个格式合法的密钥——所有会调用 OpenAI 的接口
    都会先检查这个值，再决定是否继续处理。"""
    return is_valid_format(get_settings().openai_api_key or "")


def masked_key() -> str | None:
    """The masked placeholder to show in the UI once a key is saved (or None
    if no key is configured) -- the real key is never sent back to the frontend.
    密钥保存后在界面上展示的脱敏占位符（未配置密钥时返回 None）——
    真实密钥永远不会再返回给前端。"""
    return MASKED_KEY if is_configured() else None


def save_key(raw_key: str) -> None:
    """Writes OPENAI_API_KEY into the .env file and invalidates every cached
    OpenAI client so the new key takes effect immediately, without a server
    restart.

    将 OPENAI_API_KEY 写入 .env 文件，并清空所有缓存的 OpenAI 客户端，
    让新密钥立即生效，无需重启服务。
    """
    _write_env_key(raw_key.strip())


def clear_key() -> None:
    """Blanks OPENAI_API_KEY in the .env file, putting the app back into the
    "not configured" state (upload/chat/ask/transcribe all gate on this).

    将 .env 文件中的 OPENAI_API_KEY 清空，让应用回到"未配置密钥"的状态
    （上传文档、/chat、/ask、/transcribe 都会因此被拦截）。
    """
    _write_env_key("")


def _write_env_key(key: str) -> None:
    """Shared write path for save_key()/clear_key(): updates .env, then resets
    every module's cached OpenAI client so they all pick up the change.
    save_key() 与 clear_key() 共用的写入逻辑：更新 .env 文件后，
    重置各个模块缓存的 OpenAI 客户端，让它们都能感知到这次变更。"""
    update_env_var("OPENAI_API_KEY", key)

    from app.core import asr, embeddings, tts

    asr.reset_client()
    embeddings.reset_client()
    tts.reset_client()
