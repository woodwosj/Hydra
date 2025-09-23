"""Data models for persistent tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class WorktreeRecord:
    task_id: str
    path: str
    branch: str | None
    created_at: datetime
    status: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class SessionTrackingRecord:
    session_id: str
    task_id: str | None
    profile_id: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    metadata: dict[str, Any]


__all__ = ["WorktreeRecord", "SessionTrackingRecord"]
