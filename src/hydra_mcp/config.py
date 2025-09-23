"""Configuration management for Hydra MCP."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class HydraSettings(BaseSettings):
    """Runtime configuration sourced from environment variables and optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    codex_path: str | None = Field(default=None, validation_alias="CODEX_PATH")
    codex_default_model: str | None = Field(default=None, validation_alias="CODEX_DEFAULT_MODEL")
    chroma_persist_path: Path = Field(
        default=Path("./storage/chroma"), validation_alias="CHROMA_PERSIST_PATH"
    )
    log_level: str = Field(default="INFO", validation_alias="HYDRA_LOG_LEVEL")

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError(
                "HYDRA_LOG_LEVEL must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG"
            )
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> HydraSettings:
    """Return cached settings instance."""

    settings = HydraSettings()
    settings.chroma_persist_path = settings.chroma_persist_path.expanduser().resolve()
    return settings


__all__ = ["HydraSettings", "get_settings"]
