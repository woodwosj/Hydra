
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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
        document = body if isinstance(body, str) else str(body)
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
