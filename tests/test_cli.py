from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import argparse
import importlib.util


def test_diagnostics_cli_handles_missing_chroma(tmp_path: Path) -> None:
    script = Path("scripts/hydra_diag.py").resolve()
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    fake_pkg = tmp_path / "stubs"
    chroma_pkg = fake_pkg / "chromadb"
    chroma_pkg.mkdir(parents=True)
    (chroma_pkg / "__init__.py").write_text(
        "raise ImportError('chromadb stub – simulate missing dependency')",
        encoding="utf-8",
    )
    env["PYTHONPATH"] = (
        f"{fake_pkg}" + os.pathsep + f"{repo_root / 'src'}" + os.pathsep + env.get("PYTHONPATH", "")
    )
    env["CHROMA_PERSIST_PATH"] = str(tmp_path / "chroma")
    process = subprocess.run(
        [sys.executable, str(script), "tasks"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        env=env,
    )
    assert process.returncode != 0
    assert "Chroma unavailable" in process.stdout


def test_metrics_reports_resume_counts(monkeypatch, capsys):
    class StubStore:
        def replay_tasks(self):
            return [
                {"task_id": "task-1", "status": "running"},
                {"task_id": "task-2", "status": "queued"},
            ]

        def list_worktrees(self):
            return []

        def list_session_tracking(self):
            return []

        def search_events(self, filters=None):
            if filters == {"event_type": "task_resume"}:
                return [
                    argparse.Namespace(metadata={"resume_status": "resumed", "task_id": "task-1"}),
                    argparse.Namespace(metadata={"resume_status": "resume_failed", "task_id": "task-1"}),
                    argparse.Namespace(metadata={"resume_status": "resume_failed", "task_id": "task-1"}),
                    argparse.Namespace(metadata={"resume_status": "resume_failed", "task_id": "task-1"}),
                ]
            return []

    stub = StubStore()

    def fake_load_store(_settings):
        return stub

    module_path = Path(__file__).resolve().parents[1] / "scripts" / "hydra_diag.py"
    spec = importlib.util.spec_from_file_location("hydra_diag_test_module", module_path)
    assert spec and spec.loader
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)

    monkeypatch.setattr(diag, "load_store", fake_load_store)

    diag.cmd_metrics(argparse.Namespace())

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["resume_attempts"] == 4
    assert payload["resume_status_counts"]["resumed"] == 1
    assert payload["resume_status_counts"]["resume_failed"] == 3
    assert payload["resume_alert_threshold"] == diag.HydraSettings().resume_alert_threshold
    alerts = payload["resume_failure_alerts"]
    assert alerts and alerts[0]["task_id"] == "task-1"
    assert alerts[0]["failure_count"] == 3


def test_alerts_lists_resume_alerts(monkeypatch, capsys):
    class StubStore:
        def search_events(self, filters=None):
            assert filters == {"event_type": "resume_alert"}
            return [
                argparse.Namespace(
                    id="alert-1",
                    metadata={
                        "task_id": "task-42",
                        "session_id": "sess-42",
                        "failure_count": 4,
                        "threshold": 3,
                        "resume_status": "resume_failed",
                    },
                    timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
            ]

    def fake_load_store(_settings):
        return StubStore()

    module_path = Path(__file__).resolve().parents[1] / "scripts" / "hydra_diag.py"
    spec = importlib.util.spec_from_file_location("hydra_diag_alert_module", module_path)
    assert spec and spec.loader
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)

    monkeypatch.setattr(diag, "load_store", fake_load_store)

    diag.cmd_alerts(argparse.Namespace(task_id=None, limit=None))

    output = json.loads(capsys.readouterr().out)
    assert output[0]["task_id"] == "task-42"
    assert output[0]["failure_count"] == 4


def test_alerts_limit(monkeypatch, capsys):
    class StubStore:
        def search_events(self, filters=None):
            base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
            results = []
            for idx in range(4):
                results.append(
                    argparse.Namespace(
                        id=f"alert-{idx}",
                        metadata={
                            "task_id": "task-1",
                            "session_id": f"sess-{idx}",
                            "failure_count": idx + 1,
                            "threshold": 3,
                            "resume_status": "resume_failed",
                        },
                        timestamp=base_time.replace(minute=idx),
                    )
                )
            return results

    def fake_load_store(_settings):
        return StubStore()

    module_path = Path(__file__).resolve().parents[1] / "scripts" / "hydra_diag.py"
    spec = importlib.util.spec_from_file_location("hydra_diag_alert_limit_module", module_path)
    assert spec and spec.loader
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)

    monkeypatch.setattr(diag, "load_store", fake_load_store)

    diag.cmd_alerts(argparse.Namespace(task_id=None, limit=2))

    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 2
    assert payload[0]["session_id"] == "sess-2"
    assert payload[1]["session_id"] == "sess-3"
