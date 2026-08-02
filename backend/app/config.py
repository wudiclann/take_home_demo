# App configuration, loaded from backend/.env via pydantic-settings.
# 应用配置模块，通过 pydantic-settings 从 backend/.env 文件读取配置。

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
# APP_ENV_FILE lets tests point at an isolated temp .env instead of the real one.
# APP_ENV_FILE 让测试可以指向一个隔离的临时 .env 文件，而不是真实的那一个。
ENV_FILE = Path(os.environ.get("APP_ENV_FILE", _DEFAULT_ENV_FILE))


class Settings(BaseSettings):
    """All runtime-configurable app settings, read from .env with sane defaults.
    所有可在运行时配置的应用设置，从 .env 读取，并带有合理的默认值。"""

    openai_api_key: str = ""
    tts_voice: str = "alloy"
    tts_speed: float = 1.25  # a bit faster than OpenAI's own 1.0 default / 比 OpenAI 默认的 1.0 稍快一些

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Returns the cached Settings instance -- cheap to call anywhere, only
    actually re-reads the .env file after update_env_var() clears the cache.
    返回缓存的 Settings 实例——可以在任何地方低成本调用；只有在
    update_env_var() 清空缓存后，才会真正重新读取 .env 文件。"""
    return Settings()


def update_env_var(name: str, value: str) -> None:
    """Writes NAME=value into the .env file (replacing an existing line for NAME,
    or appending one if missing), and invalidates the cached Settings so the next
    get_settings() call re-reads the file -- lets runtime-editable settings (API
    key, TTS voice/speed) take effect immediately without a server restart.

    将 NAME=value 写入 .env 文件（如果已有该变量则替换对应行，否则追加新行），
    并清空 Settings 缓存，让下一次调用 get_settings() 时重新读取文件——这样
    可在运行时修改的设置（API 密钥、TTS 音色/语速）能立即生效，无需重启服务。
    """
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    prefix = f"{name}="
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{prefix}{value}"
            updated = True
            break
    if not updated:
        lines.append(f"{prefix}{value}")
    ENV_FILE.write_text("\n".join(lines) + "\n")
    get_settings.cache_clear()
