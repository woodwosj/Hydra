from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "hydra_alert_forwarder.py"
    spec = importlib.util.spec_from_file_location("hydra_alert_forwarder_test_module", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_events():
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    event = SimpleNamespace(
        id="alert-1",
        metadata={
            "task_id": "task-42",
            "session_id": "sess-42",
            "failure_count": 4,
            "threshold": 3,
            "resume_status": "resume_failed",
        },
        timestamp=timestamp,
    )
    return [event]


def test_forward_alerts_prints_json(monkeypatch, capsys):
    module = _load_module()

    class StubStore:
        def search_events(self, *, filters):
            assert filters == {"event_type": "resume_alert"}
            return _stub_events()

    monkeypatch.setattr(module, "load_store", lambda _settings: StubStore())

    exit_code = module.forward_alerts(
        argparse.Namespace(task_id=None, format="json", output=None, limit=None)
    )
    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["task_id"] == "task-42"


def test_forward_alerts_writes_text(monkeypatch, tmp_path):
    module = _load_module()

    class StubStore:
        def search_events(self, *, filters):
            assert filters == {"event_type": "resume_alert"}
            return _stub_events()

    monkeypatch.setattr(module, "load_store", lambda _settings: StubStore())

    output_file = tmp_path / "alerts.txt"
    exit_code = module.forward_alerts(
        argparse.Namespace(task_id=None, format="text", output=str(output_file), limit=None)
    )
    assert exit_code == 0
    contents = output_file.read_text(encoding="utf-8")
    assert "task=task-42" in contents


def test_forward_alerts_filters_task(monkeypatch, capsys):
    module = _load_module()

    class StubStore:
        def search_events(self, *, filters):
            events = _stub_events()
            other = SimpleNamespace(
                id="alert-2",
                metadata={
                    "task_id": "task-99",
                    "session_id": "sess-99",
                    "failure_count": 2,
                    "threshold": 3,
                    "resume_status": "resume_failed",
                },
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
            return events + [other]

    monkeypatch.setattr(module, "load_store", lambda _settings: StubStore())

    exit_code = module.forward_alerts(
        argparse.Namespace(task_id="task-42", format="json", output=None, limit=None)
    )
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1
    assert output[0]["task_id"] == "task-42"


def test_forward_alerts_honors_limit(monkeypatch, capsys):
    module = _load_module()

    class StubStore:
        def search_events(self, *, filters):
            assert filters == {"event_type": "resume_alert"}
            base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
            events = []
            for idx in range(5):
                events.append(
                    SimpleNamespace(
                        id=f"alert-{idx}",
                        metadata={
                            "task_id": "task-42",
                            "session_id": f"sess-{idx}",
                            "failure_count": idx + 1,
                            "threshold": 3,
                            "resume_status": "resume_failed",
                        },
                        timestamp=base_time.replace(minute=idx),
                    )
                )
            return events

    monkeypatch.setattr(module, "load_store", lambda _settings: StubStore())

    exit_code = module.forward_alerts(
        argparse.Namespace(task_id=None, format="json", output=None, limit=2)
    )
    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 2
    assert data[0]["session_id"] == "sess-3"
    assert data[1]["session_id"] == "sess-4"
