"""Utility helpers for Codex runner."""

from __future__ import annotations

import os
from typing import Mapping

_SANITIZED_VARS = {
    "PYTHONHOME",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "PIP_RESPECT_VIRTUALENV",
}


def sanitize_environment(additional: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a sanitized environment suitable for subprocess execution."""

    env = dict(os.environ)
    for key in _SANITIZED_VARS:
        env.pop(key, None)
    if additional:
        env.update(additional)
    return env

