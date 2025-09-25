"""Configuration management for Hydra MCP."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os

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
    profile_paths: tuple[Path, ...] = Field(
        default=(Path("profiles"),), validation_alias="HYDRA_PROFILE_PATHS"
    )
    log_level: str = Field(default="INFO", validation_alias="HYDRA_LOG_LEVEL")
    resume_alert_threshold: int = Field(
        default=3, validation_alias="HYDRA_RESUME_ALERT_THRESHOLD"
    )

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError(
                "HYDRA_LOG_LEVEL must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG"
            )
        return normalized

    @field_validator("profile_paths", mode="before")
    @classmethod
    def _parse_profile_paths(cls, value):
        if value is None or value == "":
            return (Path("profiles"),)
        if isinstance(value, (list, tuple)):
            return tuple(Path(str(item)) for item in value)
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(os.pathsep) if part.strip()]
            return tuple(Path(part) for part in parts) or (Path("profiles"),)
        raise TypeError("HYDRA_PROFILE_PATHS must be a list of paths or a path-separated string")

    @field_validator("resume_alert_threshold")
    @classmethod
    def _validate_resume_alert_threshold(cls, value: int) -> int:
        if value < 1:
            raise ValueError("HYDRA_RESUME_ALERT_THRESHOLD must be >= 1")
        return value


@lru_cache(maxsize=1)
def get_settings() -> HydraSettings:
    """Return cached settings instance."""

    settings = HydraSettings()
    settings.chroma_persist_path = settings.chroma_persist_path.expanduser().resolve()
    settings.profile_paths = tuple(path.expanduser().resolve() for path in settings.profile_paths)
    return settings


__all__ = ["HydraSettings", "get_settings"]
