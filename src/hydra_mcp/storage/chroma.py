"""Chroma-based persistence layer."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from .models import SessionTrackingRecord, WorktreeRecord

class ChromaUnavailableError(RuntimeError):
    """Raised when the Chroma client cannot be constructed."""


class CollectionProtocol(Protocol):
    """Protocol for the minimal Chroma collection API used by Hydra."""

    def add(
        self,
        *,
        documents: Iterable[str],
        metadatas: Iterable[dict[str, Any]],
        ids: Iterable[str],
    ) -> None:
        ...

    def get(
        self,
        *,
        ids: Iterable[str] | None = None,
        where: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> dict[str, list[Any]]:
        ...


class ClientProtocol(Protocol):
    """Protocol for the minimal Chroma client API used by Hydra."""

    def get_or_create_collection(self, name: str) -> CollectionProtocol:
        ...


@dataclass(slots=True)
class ChromaEvent:
    """Represents a stored event in Chroma."""

    id: str
    session_id: str
    event_type: str
    document: str
    metadata: dict[str, Any]
    timestamp: datetime


class ChromaStore:
    """Manage persistence of session events via ChromaDB."""

    def __init__(
        self,
        path: Path,
        *,
        collection_name: str = "hydra_runs",
        client_factory: Callable[[], ClientProtocol] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._path = Path(path)
        self._collection_name = collection_name
        self._client_factory = client_factory or self._default_client_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._client: ClientProtocol | None = None
        self._collection: CollectionProtocol | None = None
        self._counters: dict[str, int] = defaultdict(int)

    def _default_client_factory(self) -> ClientProtocol:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ChromaUnavailableError(
                "chromadb package is not installed; install hydra with persistence extras"
            ) from exc

        return chromadb.PersistentClient(path=str(self._path))

    def _ensure_collection(self) -> CollectionProtocol:
        if self._collection is None:
            client = self._client or self._client_factory()
            self._client = client
            self._collection = client.get_or_create_collection(self._collection_name)
        return self._collection

    def _convert_result(self, result: dict[str, list[Any]]) -> list[ChromaEvent]:
        events: list[ChromaEvent] = []
        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        for event_id, document, metadata in zip(ids, documents, metadatas):
            timestamp_raw = metadata.get("timestamp")
            timestamp = (
                datetime.fromisoformat(timestamp_raw)
                if isinstance(timestamp_raw, str)
                else self._clock()
            )
            events.append(
                ChromaEvent(
                    id=event_id,
                    session_id=metadata.get("session_id", ""),
                    event_type=metadata.get("event_type", ""),
                    document=document,
                    metadata=metadata,
                    timestamp=timestamp,
                )
            )
        events.sort(key=lambda event: event.metadata.get("sequence", 0))
        return events

    def ping(self) -> bool:
        """Verify that the underlying collection can be obtained."""

        self._ensure_collection()
        return True

    def record_event(
        self,
        *,
        session_id: str,
        event_type: str,
        body: Any,
        metadata: dict[str, Any] | None = None,
    ) -> ChromaEvent:
        collection = self._ensure_collection()
        counter = self._counters[session_id] = self._counters[session_id] + 1
        event_id = f"{session_id}:{uuid.uuid4().hex}"
        timestamp = self._clock()

        document = body if isinstance(body, str) else json.dumps(body)
        record_metadata = {
            "session_id": session_id,
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
            "sequence": counter,
        }
        if metadata:
            record_metadata.update(metadata)

        collection.add(
            documents=[document],
            metadatas=[record_metadata],
            ids=[event_id],
        )

        return ChromaEvent(
            id=event_id,
            session_id=session_id,
            event_type=event_type,
            document=document,
            metadata=record_metadata,
            timestamp=timestamp,
        )

    def fetch_session_events(self, session_id: str, *, limit: int | None = None) -> list[ChromaEvent]:
        collection = self._ensure_collection()
        result = collection.get(where={"session_id": session_id}, limit=limit)
        return self._convert_result(result)

    def record_worktree(
        self,
        *,
        task_id: str,
        path: str,
        branch: str | None,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorktreeRecord:
        timestamp = self._clock()
        payload = {
            "task_id": task_id,
            "path": path,
            "branch": branch,
            "status": status,
            "timestamp": timestamp.isoformat(),
        }
        if metadata:
            payload.update(metadata)

        event = self.record_event(
            session_id=f"worktree::{task_id}",
            event_type="worktree_update",
            body=payload,
            metadata={"task_id": task_id, "path": path, "status": status},
        )

        return WorktreeRecord(
            task_id=task_id,
            path=path,
            branch=branch,
            created_at=event.timestamp,
            status=status,
            metadata=metadata or {},
        )

    def list_worktrees(self, task_id: str | None = None) -> list[WorktreeRecord]:
        filters = {"task_id": task_id} if task_id else None
        events = self.search_events("worktree", filters=filters)
        worktrees: list[WorktreeRecord] = []
        for event in events:
            doc = json.loads(event.document)
            worktrees.append(
                WorktreeRecord(
                    task_id=doc["task_id"],
                    path=doc["path"],
                    branch=doc.get("branch"),
                    created_at=event.timestamp,
                    status=doc.get("status", "unknown"),
                    metadata={k: v for k, v in doc.items() if k not in {"task_id", "path", "branch", "status", "timestamp"}},
                )
            )
        return worktrees

    def record_session_tracking(
        self,
        *,
        session_id: str,
        profile_id: str,
        status: str,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionTrackingRecord:
        timestamp = self._clock()
        payload = {
            "session_id": session_id,
            "profile_id": profile_id,
            "task_id": task_id,
            "status": status,
            "timestamp": timestamp.isoformat(),
        }
        if metadata:
            payload.update(metadata)

        event = self.record_event(
            session_id=f"session::{session_id}",
            event_type="session_tracking",
            body=payload,
            metadata={
                "session_id": session_id,
                "profile_id": profile_id,
                "task_id": task_id,
                "status": status,
            },
        )

        return SessionTrackingRecord(
            session_id=session_id,
            task_id=task_id,
            profile_id=profile_id,
            started_at=event.timestamp,
            completed_at=None,
            status=status,
            metadata=metadata or {},
        )

    def list_session_tracking(self, task_id: str | None = None) -> list[SessionTrackingRecord]:
        filters = {"task_id": task_id} if task_id else None
        events = self.search_events(filters=filters, query=None)
        sessions: list[SessionTrackingRecord] = []
        for event in events:
            if event.event_type != "session_tracking":
                continue
            doc = json.loads(event.document)
            sessions.append(
                SessionTrackingRecord(
                    session_id=doc["session_id"],
                    task_id=doc.get("task_id"),
                    profile_id=doc["profile_id"],
                    started_at=event.timestamp,
                    completed_at=None,
                    status=doc.get("status", "unknown"),
                    metadata={k: v for k, v in doc.items() if k not in {"session_id", "profile_id", "task_id", "status", "timestamp"}},
                )
            )
        return sessions

    def replay_tasks(self) -> list[dict[str, Any]]:
        """Reconstruct task state from persisted events."""

        created_events = self.search_events(query=None, filters={"event_type": "task_created"})
        tasks: dict[str, dict[str, Any]] = {}

        for event in created_events:
            doc = json.loads(event.document)
            task_id = doc.get("task_id")
            if not task_id:
                continue

            history = self.search_events(query=None, filters={"task_id": task_id})
            latest_event = history[-1] if history else event
            latest_doc = json.loads(latest_event.document)

            tasks[task_id] = {
                "task_id": task_id,
                "profile_id": doc.get("profile_id"),
                "task_brief": doc.get("task_brief"),
                "status": latest_event.metadata.get("status")
                or latest_doc.get("status")
                or "pending",
                "session_id": latest_doc.get("session_id"),
                "context_package": doc.get("context_package", {}),
                "metadata": doc.get("metadata", {}),
                "created_at": event.timestamp.isoformat(),
                "updated_at": latest_event.timestamp.isoformat(),
            }

        return list(tasks.values())

    def search_events(
        self,
        query: str | None = None,
        *,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[ChromaEvent]:
        collection = self._ensure_collection()
        result = collection.get(where=filters, limit=limit)
        events = self._convert_result(result)
        if query:
            needle = query.lower()
            filtered: list[ChromaEvent] = []
            for event in events:
                haystacks = [event.document.lower()]
                for value in event.metadata.values():
                    if isinstance(value, str):
                        haystacks.append(value.lower())
                    elif not isinstance(value, (int, float, bool, type(None))):
                        haystacks.append(str(value).lower())
                    else:
                        haystacks.append(str(value).lower())
                if any(needle in hay for hay in haystacks):
                    filtered.append(event)
            events = filtered
        return events[:limit] if limit else events


__all__ = ["ChromaEvent", "ChromaStore", "ChromaUnavailableError"]
