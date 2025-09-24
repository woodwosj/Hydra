from __future__ import annotations

from types import SimpleNamespace

import pytest

try:
    from hydra_mcp.server import create_server
    from hydra_mcp.config import HydraSettings
except ModuleNotFoundError:
    pytest.skip("fastmcp not installed", allow_module_level=True)


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
    assert getattr(server, "resume_actions")[-1]["status"] == "resumed"
