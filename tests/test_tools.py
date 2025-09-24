
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
import json

from hydra_mcp.codex.runner import CodexExecutionResult
from hydra_mcp.config import HydraSettings
from hydra_mcp.profiles import AgentProfile, ChecklistItem
from hydra_mcp.tools import register_tools


class StubTool:
    def __init__(self, fn, name):
        self.fn = fn
        self.name = name


class StubServer:
    def __init__(self) -> None:
        self._tools: dict[str, StubTool] = {}

    def tool(self, *args, **kwargs):
        provided_name = None
        if args and isinstance(args[0], str):
            provided_name = args[0]
        provided_name = kwargs.get("name", provided_name)

        def decorator(fn):
            tool_name = provided_name or fn.__name__
            tool = StubTool(fn, tool_name)
            self._tools[tool_name] = tool
            return tool

        return decorator


class StubProfileLoader:
    def __init__(self, profile: AgentProfile) -> None:
        self._profile = profile

    def load_all(self) -> dict[str, AgentProfile]:
        return {self._profile.id: self._profile}


class StubCodexRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def spawn(self, command: str, *, flags: list[str] | None = None) -> CodexExecutionResult:
        self.calls.append({"command": command, "flags": flags or []})
        return CodexExecutionResult(
            args=("codex", "exec"),
            returncode=0,
            stdout="mock output",
            stderr="",
        )


@dataclass
class StubEvent:
    id: str
    session_id: str
    event_type: str
    document: str
    metadata: dict[str, Any]
    timestamp: datetime


class StubChromaStore:
    def __init__(self) -> None:
        self.events: list[StubEvent] = []
        self._counter = 0

    def ping(self) -> bool:
        return True

    def record_event(self, *, session_id: str, event_type: str, body: Any, metadata: dict[str, Any]) -> StubEvent:
        self._counter += 1
        merged = metadata.copy()
        merged.setdefault("sequence", self._counter)
        merged.setdefault("timestamp", datetime.fromisoformat("2025-01-01T00:00:00+00:00").isoformat())
        merged.setdefault("session_id", session_id)
        merged.setdefault("event_type", event_type)
        document = body if isinstance(body, str) else json.dumps(body)
        event = StubEvent(
            id=f"{session_id}:{self._counter}",
            session_id=session_id,
            event_type=event_type,
            document=document,
            metadata=merged,
            timestamp=datetime.fromisoformat(merged["timestamp"]),
        )
        self.events.append(event)
        return event

    def fetch_session_events(self, session_id: str, *, limit: int | None = None) -> list[StubEvent]:
        filtered = [event for event in self.events if event.session_id == session_id]
        if limit is not None:
            filtered = filtered[:limit]
        return filtered

    def search_events(
        self,
        query: str | None = None,
        *,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[StubEvent]:
        results = self.events
        if filters:
            for key, value in filters.items():
                results = [event for event in results if event.metadata.get(key) == value]
        if query:
            needle = query.lower()
            results = [
                event
                for event in results
                if needle in event.document.lower()
                or any(needle in str(val).lower() for val in event.metadata.values())
            ]
        if limit is not None:
            results = results[:limit]
        return results

    def record_worktree(
        self,
        *,
        task_id: str,
        path: str,
        branch: str | None,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "task_id": task_id,
            "path": path,
            "branch": branch,
            "status": status,
        }
        if metadata:
            payload.update(metadata)
        self.record_event(
            session_id=f"worktree::{task_id}",
            event_type="worktree_update",
            body=payload,
            metadata={"task_id": task_id, "status": status, "event_type": "worktree_update"},
        )

    def list_worktrees(self, task_id: str | None = None):
        records = []
        for event in self.events:
            if event.event_type != "worktree_update":
                continue
            if task_id and event.metadata.get("task_id") != task_id:
                continue
            doc = json.loads(event.document)
            records.append(
                type(
                    "Worktree",
                    (),
                    {
                        "task_id": doc["task_id"],
                        "path": doc["path"],
                        "branch": doc.get("branch"),
                        "status": doc.get("status", "unknown"),
                        "metadata": {k: v for k, v in doc.items() if k not in {"task_id", "path", "branch", "status", "timestamp"}},
                    },
                )()
            )
        return records

    def record_session_tracking(
        self,
        *,
        session_id: str,
        profile_id: str,
        status: str,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "session_id": session_id,
            "profile_id": profile_id,
            "task_id": task_id,
            "status": status,
        }
        if metadata:
            payload.update(metadata)
        record_meta = {
            "session_id": session_id,
            "profile_id": profile_id,
            "task_id": task_id,
            "status": status,
            "event_type": "session_tracking",
        }
        self.record_event(
            session_id=f"session::{session_id}",
            event_type="session_tracking",
            body=payload,
            metadata=record_meta,
        )

    def list_session_tracking(self, task_id: str | None = None):
        results = []
        for event in self.events:
            if event.event_type != "session_tracking":
                continue
            if task_id and event.metadata.get("task_id") != task_id:
                continue
            doc = json.loads(event.document)
            results.append(
                type(
                    "Record",
                    (),
                    {
                        "session_id": doc["session_id"],
                        "profile_id": doc["profile_id"],
                        "task_id": doc.get("task_id"),
                        "status": doc.get("status", "unknown"),
                        "started_at": event.timestamp,
                    },
                )()
            )
        return results

    def replay_tasks(self) -> list[dict[str, Any]]:
        tasks: dict[str, dict[str, Any]] = {}
        for event in self.events:
            if event.metadata.get("event_type") != "task_created":
                continue
            doc = json.loads(event.document)
            task_id = doc.get("task_id")
            if not task_id:
                continue
            history = [e for e in self.events if e.metadata.get("task_id") == task_id]
            latest = history[-1] if history else event
            latest_doc = json.loads(latest.document) if latest.document.startswith("{") else {}
            tasks[task_id] = {
                "task_id": task_id,
                "profile_id": doc.get("profile_id"),
                "task_brief": doc.get("task_brief"),
                "status": latest.metadata.get("status") or latest_doc.get("status", "pending"),
                "session_id": latest_doc.get("session_id"),
                "context_package": doc.get("context_package", {}),
                "metadata": doc.get("metadata", {}),
                "created_at": event.timestamp.isoformat(),
                "updated_at": latest.timestamp.isoformat(),
            }
        return list(tasks.values())

    def record_worktree(
        self,
        *,
        task_id: str,
        path: str,
        branch: str | None,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "task_id": task_id,
            "path": path,
            "branch": branch,
            "status": status,
        }
        if metadata:
            payload.update(metadata)
        self.record_event(
            session_id=f"worktree::{task_id}",
            event_type="worktree_update",
            body=payload,
            metadata={"task_id": task_id, "status": status},
        )

    def record_session_tracking(
        self,
        *,
        session_id: str,
        profile_id: str,
        status: str,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "session_id": session_id,
            "profile_id": profile_id,
            "task_id": task_id,
            "status": status,
        }
        if metadata:
            payload.update(metadata)
        record_meta = {"session_id": session_id, "profile_id": profile_id, "task_id": task_id, "status": status}
        self.record_event(
            session_id=f"session::{session_id}",
            event_type="session_tracking",
            body=payload,
            metadata=record_meta,
        )


def _make_profile(profile_id: str = "generalist") -> AgentProfile:
    return AgentProfile(
        id=profile_id,
        title="Generalist" if profile_id == "generalist" else "Reviewer",
        persona="Persona",
        system_prompt="Do work",
        goalset=["goal"],
        constraints=["constraint"],
        checklist_template=[ChecklistItem(id="step", description="do it")],
    )


def test_spawn_agent_records_event() -> None:
    profile = _make_profile()
    loader = StubProfileLoader(profile)
    runner = StubCodexRunner()
    chroma = StubChromaStore()

    server = StubServer()
    settings = HydraSettings()
    settings.codex_default_model = "gpt-test"
    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=runner,
        chroma_store=chroma,  # type: ignore[arg-type]
    )

    result = asyncio.run(
        handles.spawn_agent.fn(  # type: ignore[attr-defined]
            profile_id="generalist",
            task_brief="Build feature",
            goalset=["ship"],
        )
    )

    assert result["returncode"] == 0
    assert runner.calls[0]["flags"][0] == "--model"
    assert chroma.events and chroma.events[0].event_type == "spawn_agent"


def test_list_agents_reports_catalog() -> None:
    profile = _make_profile("code_reviewer")
    loader = StubProfileLoader(profile)
    server = StubServer()
    settings = HydraSettings()

    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=None,
        chroma_store=None,
    )

    catalog = handles.list_agents.fn()  # type: ignore[attr-defined]

    assert catalog[0]["id"] == "code_reviewer"


def test_log_context_and_summarize() -> None:
    profile = _make_profile()
    loader = StubProfileLoader(profile)
    chroma = StubChromaStore()

    server = StubServer()
    settings = HydraSettings()
    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=None,
        chroma_store=chroma,  # type: ignore[arg-type]
    )

    # Manually seed spawn event to simulate prior work
    chroma.record_event(
        session_id="generalist-1",
        event_type="spawn_agent",
        body={},
        metadata={"sequence": 1},
    )

    log_result = handles.log_context.fn(  # type: ignore[attr-defined]
        session_id="generalist-1",
        title="Docs",
        notes="Link to docs",
        tags=["reference"],
    )

    assert "event_id" in log_result

    summary = handles.summarize_session.fn("generalist-1")  # type: ignore[attr-defined]
    assert summary["event_count"] == 2
    assert "timeline_preview" in summary


def test_query_context_returns_match() -> None:
    profile = _make_profile()
    loader = StubProfileLoader(profile)
    chroma = StubChromaStore()
    chroma.record_event(
        session_id="generalist-1",
        event_type="note",
        body="Investigate latency",
        metadata={"sequence": 1, "topic": "latency"},
    )
    chroma.record_event(
        session_id="generalist-1",
        event_type="note",
        body="Fix auth bug",
        metadata={"sequence": 2, "topic": "auth"},
    )

    server = StubServer()
    settings = HydraSettings()
    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=None,
        chroma_store=chroma,  # type: ignore[arg-type]
    )

    result = handles.query_context.fn("auth", session_id="generalist-1")  # type: ignore[attr-defined]
    assert len(result["matches"]) == 1
    assert result["matches"][0]["metadata"]["topic"] == "auth"


def test_terminate_session_records_reason() -> None:
    profile = _make_profile()
    loader = StubProfileLoader(profile)
    chroma = StubChromaStore()

    server = StubServer()
    settings = HydraSettings()
    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=None,
        chroma_store=chroma,  # type: ignore[arg-type]
    )

    result = asyncio.run(  # type: ignore[attr-defined]
        handles.terminate_session.fn(  # type: ignore[attr-defined]
            session_id="generalist-1",
            reason="User cancelled",
        )
    )
    assert result["reason"] == "User cancelled"
    assert any(event.event_type == "terminate_session" for event in chroma.events)


def test_export_session_markdown() -> None:
    profile = _make_profile()
    loader = StubProfileLoader(profile)
    chroma = StubChromaStore()
    chroma.record_event(
        session_id="generalist-1",
        event_type="note",
        body="Initial note",
        metadata={"sequence": 1},
    )

    server = StubServer()
    settings = HydraSettings()
    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=None,
        chroma_store=chroma,  # type: ignore[arg-type]
    )

    export = handles.export_session.fn("generalist-1", format="markdown")  # type: ignore[attr-defined]
    assert export["format"] == "markdown"
    assert "Initial note" in export["data"]


def test_register_tools_hydrates_tasks() -> None:
    profile = _make_profile()
    loader = StubProfileLoader(profile)
    chroma = StubChromaStore()

    chroma.record_event(
        session_id="task::task-hyd-1",
        event_type="task_created",
        body={
            "task_id": "task-hyd-1",
            "status": "pending",
            "profile_id": "generalist",
            "task_brief": "Persist state",
            "context_package": {"files": ["src/hydra_mcp"]},
            "metadata": {"priority": "P0"},
        },
        metadata={"task_id": "task-hyd-1", "status": "pending", "event_type": "task_created"},
    )

    chroma.record_event(
        session_id="task::task-hyd-1",
        event_type="task_started",
        body={
            "task_id": "task-hyd-1",
            "status": "running",
            "session_id": "generalist-2025",
        },
        metadata={"task_id": "task-hyd-1", "status": "running", "event_type": "task_started"},
    )

    server = StubServer()
    settings = HydraSettings()

    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=None,
        chroma_store=chroma,  # type: ignore[arg-type]
    )

    assert "task-hyd-1" in handles.tasks_state
    assert handles.tasks_state["task-hyd-1"]["status"] == "running"
    assert handles.tasks_state["task-hyd-1"]["session_id"] == "generalist-2025"


def test_task_lifecycle() -> None:
    profile = _make_profile()
    loader = StubProfileLoader(profile)
    chroma = StubChromaStore()
    runner = StubCodexRunner()

    server = StubServer()
    settings = HydraSettings()
    settings.codex_default_model = "gpt-test"
    handles = register_tools(
        server,  # type: ignore[arg-type]
        profiles=loader,
        settings=settings,
        codex_runner=runner,
        chroma_store=chroma,  # type: ignore[arg-type]
    )

    task = handles.create_task.fn(  # type: ignore[attr-defined]
        profile_id="generalist",
        task_brief="Implement feature",
        context_package={"files": ["src/app.py"], "worktree_path": "/tmp/work", "worktree_branch": "feature"},
        metadata={"priority": "high"},
    )

    assert task["status"] == "pending"
    assert len(handles.tasks_state) == 1

    start_result = asyncio.run(  # type: ignore[attr-defined]
        handles.start_task.fn(task_id=task["task_id"])  # type: ignore[attr-defined]
    )
    assert start_result["task"]["status"] == "running"
    assert runner.calls, "Codex runner should have been invoked"
    assert any(event.event_type == "session_tracking" for event in chroma.events)

    status = handles.task_status.fn(task["task_id"])  # type: ignore[attr-defined]
    assert status["status"] == "running"

    completed = handles.complete_task.fn(  # type: ignore[attr-defined]
        task["task_id"],
        outcome="completed",
        summary="All tests passing",
    )
    assert completed["status"] == "completed"
    assert any(event.event_type == "task_completed" for event in chroma.events)
    assert any(event.event_type == "worktree_update" for event in chroma.events)
