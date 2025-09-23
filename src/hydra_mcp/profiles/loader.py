"""Profile loading utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
from pydantic import ValidationError

from .models import AgentProfile


class ProfileLoadError(RuntimeError):
    """Raised when one or more profile files cannot be parsed."""


class ProfileLoader:
    """Loads agent profiles from YAML files on disk."""

    def __init__(self, search_paths: Iterable[Path] | None = None) -> None:
        paths = [Path(path) for path in (search_paths or [])]
        self._search_paths: list[Path] = [path for path in paths if path.exists()]

    @property
    def search_paths(self) -> list[Path]:
        """Return the normalized search paths."""

        return list(self._search_paths)

    def load_all(self) -> dict[str, AgentProfile]:
        """Load profiles from all configured search paths.

        Later search paths override earlier ones when profile ids collide.
        """

        if not self._search_paths:
            return {}

        profiles: dict[str, AgentProfile] = {}
        errors: list[str] = []

        for base in self._search_paths:
            for path in sorted(base.glob("*.yml")) + sorted(base.glob("*.yaml")):
                try:
                    document = yaml.safe_load(path.read_text(encoding="utf-8"))
                except yaml.YAMLError as exc:  # pragma: no cover - library type
                    errors.append(f"Failed to parse YAML in {path}: {exc}")
                    continue

                if document is None:
                    continue

                try:
                    profile = AgentProfile.model_validate(document)
                except ValidationError as exc:
                    errors.append(f"Profile validation error in {path}: {exc}")
                    continue

                profiles[profile.id] = profile

        if errors:
            raise ProfileLoadError("; ".join(errors))

        return profiles

    def get(self, profile_id: str) -> AgentProfile:
        """Return a single profile by id."""

        profiles = self.load_all()
        try:
            return profiles[profile_id]
        except KeyError as exc:  # pragma: no cover - simple branch
            raise ProfileLoadError(f"Profile '{profile_id}' not found in search paths") from exc


def load_profiles(search_paths: Iterable[Path] | None = None) -> dict[str, AgentProfile]:
    """Convenience wrapper for loading profiles from the provided paths."""

    loader = ProfileLoader(search_paths)
    return loader.load_all()


__all__ = ["AgentProfile", "ProfileLoadError", "ProfileLoader", "load_profiles"]
