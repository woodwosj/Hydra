from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import json
import sys
import types

import pytest


if "fastmcp" not in sys.modules:
    stub_module = types.ModuleType("fastmcp")

    class _StubContext:  # pragma: no cover - simple placeholder
        request_id = None

    class _StubFastMCP:
        def __init__(self, *args, **kwargs):
            self._tools = []

        def resource(self, *args, **kwargs):
            def decorator(fn):
                name = kwargs.get("name") or (args[0] if args else fn.__name__)
                setattr(self, name, fn)
                return fn

            return decorator

        def tool(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

        def run(self):  # pragma: no cover - not used in tests
            return None

    stub_module.Context = _StubContext
    stub_module.FastMCP = _StubFastMCP
    sys.modules["fastmcp"] = stub_module

from hydra_mcp.server import create_server
from hydra_mcp.config import HydraSettings


class StubChromaStore:
    last_instance: "StubChromaStore | None" = None

    def __init__(self, *_, **__):
        self.events: list[dict[str, object]] = []
        StubChromaStore.last_instance = self

    def ping(self) -> bool:
        return True

    def record_event(self, *, session_id, event_type, body, metadata):
        event = {
            "session_id": session_id,
            "event_type": event_type,
            "body": body,
            "metadata": metadata,
            "timestamp": datetime.now(timezone.utc),
        }
        self.events.append(event)
        return SimpleNamespace(id=f"event-{len(self.events)}", timestamp=event["timestamp"])

    def list_worktrees(self, *_, **__):
        return []

    def list_session_tracking(self, *_, **__):
        return []

    def replay_tasks(self):
        return []


class FakeRunner:
    def __init__(self) -> None:
        self.resumed: list[str] = []

    async def version(self):
        class Result:
            ok = True
            stdout = "codex-test"
            returncode = 0

        return Result()

    async def resume(self, session_id: str):
        self.resumed.append(session_id)

        class Result:
            ok = True
            stdout = "resume ok"
            returncode = 0

        return Result()


def test_create_server_resume_actions(monkeypatch):
    settings = HydraSettings()
    fake_runner = FakeRunner()

    monkeypatch.setattr("hydra_mcp.server.ChromaStore", StubChromaStore)

    def fake_register_tools(*_, **__):
        task = {
            "task_id": "task-hyd-1",
            "profile_id": "generalist",
            "status": "running",
            "session_id": "sess-1",
            "task_brief": "Resume me",
            "metadata": {},
            "created_at": "2025-09-23T00:00:00Z",
            "updated_at": "2025-09-23T00:00:00Z",
        }
        return SimpleNamespace(
            spawn_agent=None,
            list_agents=None,
            summarize_session=None,
            log_context=None,
            query_context=None,
            terminate_session=None,
            export_session=None,
            create_task=None,
            start_task=None,
            task_status=None,
            complete_task=None,
            tasks_state={"task-hyd-1": task},
            session_state={},
            worktree_state={},
        )

    monkeypatch.setattr("hydra_mcp.server.register_tools", fake_register_tools)

    server = create_server(settings, codex_runner=fake_runner)

    assert fake_runner.resumed == ["sess-1"]
    action = getattr(server, "resume_actions")[-1]
    assert action["status"] == "resumed"
    assert "attempted_at" in action
    assert getattr(server, "tasks_state")["task-hyd-1"]["resume_failure_count"] == 0
    status_payload = json.loads(server.hydra_status(None))
    assert status_payload["tasks"]["resume_metrics"]["active_alert_count"] == 0


def test_create_server_resume_failure_increments(monkeypatch, caplog):
    settings = HydraSettings()
    settings.resume_alert_threshold = 1

    monkeypatch.setattr("hydra_mcp.server.ChromaStore", StubChromaStore)
    caplog.set_level("WARNING", logger="hydra_mcp.server")

    class FailingRunner:
        async def version(self):
            class Result:
                ok = True
                stdout = "codex-test"
                returncode = 0

            return Result()

        async def resume(self, session_id: str):
            class Result:
                ok = False
                stdout = "resume failed"
                returncode = 1

            return Result()

    def fake_register_tools(*_, **__):
        task = {
            "task_id": "task-hyd-2",
            "profile_id": "generalist",
            "status": "running",
            "session_id": "sess-2",
            "task_brief": "Resume me",
            "metadata": {},
            "created_at": "2025-09-23T00:00:00Z",
            "updated_at": "2025-09-23T00:00:00Z",
        }
        return SimpleNamespace(
            spawn_agent=None,
            list_agents=None,
            summarize_session=None,
            log_context=None,
            query_context=None,
            terminate_session=None,
            export_session=None,
            create_task=None,
            start_task=None,
            task_status=None,
            complete_task=None,
            tasks_state={"task-hyd-2": task},
            session_state={},
            worktree_state={},
        )

    monkeypatch.setattr("hydra_mcp.server.register_tools", fake_register_tools)

    server = create_server(settings, codex_runner=FailingRunner())

    action = getattr(server, "resume_actions")[-1]
    assert action["status"] == "resume_failed"
    assert action["failure_count"] == 1
    task_state = getattr(server, "tasks_state")["task-hyd-2"]
    assert task_state["status"] == "queued"
    assert task_state["resume_failure_count"] == 1
    stub_store = StubChromaStore.last_instance
    assert stub_store is not None
    alert_events = [event for event in stub_store.events if event["event_type"] == "resume_alert"]
    assert alert_events and alert_events[0]["metadata"]["failure_count"] == 1
    assert any(
        record.levelname == "WARNING" and "Resume failures exceeded threshold" in record.getMessage()
        for record in caplog.records
    )
    status_payload = json.loads(server.hydra_status(None))
    metrics = status_payload["tasks"]["resume_metrics"]
    assert metrics["active_alert_count"] == 1
    assert metrics["most_recent_alert"]["task_id"] == "task-hyd-2"
