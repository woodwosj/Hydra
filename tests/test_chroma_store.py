from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from hydra_mcp.storage import ChromaEvent, ChromaStore, WorktreeRecord, SessionTrackingRecord


@dataclass
class _Record:
    document: str
    metadata: dict[str, Any]
    id: str


class StubCollection:
    def __init__(self) -> None:
        self.records: list[_Record] = []

    def add(self, *, documents, metadatas, ids) -> None:  # type: ignore[override]
        for document, metadata, record_id in zip(documents, metadatas, ids):
            self.records.append(_Record(document=document, metadata=dict(metadata), id=record_id))

    def get(self, *, ids=None, where=None, limit=None):  # type: ignore[override]
        filtered = self.records
        if where:
            for key, value in where.items():
                filtered = [record for record in filtered if record.metadata.get(key) == value]
        if limit is not None:
            filtered = filtered[:limit]
        return {
            "ids": [record.id for record in filtered],
            "documents": [record.document for record in filtered],
            "metadatas": [record.metadata for record in filtered],
        }


class StubClient:
    def __init__(self) -> None:
        self.collections = defaultdict(StubCollection)

    def get_or_create_collection(self, name: str) -> StubCollection:
        return self.collections[name]


def test_record_and_fetch_events(tmp_path: Path) -> None:
    store = ChromaStore(
        tmp_path,
        client_factory=lambda: StubClient(),
        clock=lambda: datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
    )

    event = store.record_event(
        session_id="session-1",
        event_type="log",
        body={"message": "started"},
        metadata={"level": "INFO"},
    )

    assert event.session_id == "session-1"
    assert event.metadata["sequence"] == 1

    events = store.fetch_session_events("session-1")
    assert len(events) == 1
    assert events[0].metadata["level"] == "INFO"
    assert events[0].document == '{"message": "started"}'


def test_sequence_increments(tmp_path: Path) -> None:
    store = ChromaStore(
        tmp_path,
        client_factory=lambda: StubClient(),
        clock=lambda: datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
    )

    store.record_event(session_id="session-2", event_type="a", body="A")
    store.record_event(session_id="session-2", event_type="b", body="B")

    events = store.fetch_session_events("session-2")
    sequences = [event.metadata["sequence"] for event in events]
    assert sequences == [1, 2]



def test_search_filters(tmp_path: Path) -> None:
    store = ChromaStore(
        tmp_path,
        client_factory=lambda: StubClient(),
        clock=lambda: datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
    )

    store.record_event(session_id="sess", event_type="note", body="Investigate auth", metadata={"tags": ["auth"]})
    store.record_event(session_id="sess", event_type="note", body="Fix logging", metadata={})

    results = store.search_events("auth")
    assert len(results) == 1
    assert "auth" in results[0].document



def test_worktree_recording(tmp_path: Path) -> None:
    store = ChromaStore(
        tmp_path,
        client_factory=lambda: StubClient(),
        clock=lambda: datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
    )

    record = store.record_worktree(task_id="task1", path="/tmp/work", branch="feature", status="active")
    assert isinstance(record, WorktreeRecord)
    worktrees = store.list_worktrees("task1")
    assert worktrees[0].path == "/tmp/work"


def test_session_tracking(tmp_path: Path) -> None:
    store = ChromaStore(
        tmp_path,
        client_factory=lambda: StubClient(),
        clock=lambda: datetime.fromisoformat("2025-01-01T00:00:00+00:00"),
    )

    record = store.record_session_tracking(session_id="sess1", profile_id="generalist", status="running", task_id="task1")
    assert isinstance(record, SessionTrackingRecord)
    sessions = store.list_session_tracking("task1")
    assert sessions[0].session_id == "sess1"
