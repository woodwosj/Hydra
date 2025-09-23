from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from hydra_mcp.codex.runner import (
    CodexExecutionResult,
    CodexNotFoundError,
    CodexRunner,
    FakeCodexRunner,
    serialize_result,
)
from hydra_mcp.codex.utils import sanitize_environment


def test_codex_runner_executes_script(tmp_path: Path) -> None:
    script = tmp_path / "codex"
    script.write_text("#!/bin/sh\necho 'Codex CLI 0.0.1'\n", encoding="utf-8")
    script.chmod(0o755)

    runner = CodexRunner(script)
    result = asyncio.run(runner.version())

    assert result.ok
    assert "Codex CLI 0.0.1" in result.stdout


def test_codex_spawn_passes_flags(tmp_path: Path) -> None:
    script = tmp_path / "codex"
    script.write_text("#!/bin/sh\necho \"$@\"\n", encoding="utf-8")
    script.chmod(0o755)

    runner = CodexRunner(script)
    result = asyncio.run(runner.spawn("status", flags=["--model", "gpt"]))

    assert result.ok
    assert "--model gpt exec status" in result.stdout.strip()


def test_codex_not_found(tmp_path: Path) -> None:
    with pytest.raises(CodexNotFoundError):
        CodexRunner(tmp_path / "missing")


def test_fake_codex_runner_records_invocations() -> None:
    fake = FakeCodexRunner(
        [
            CodexExecutionResult(args=("exec",), returncode=0, stdout="ok", stderr=""),
        ]
    )

    result = asyncio.run(fake._invoke("exec"))

    assert result.stdout == "ok"
    assert fake.invocations == [("exec",)]


def test_serialize_result_roundtrip() -> None:
    result = CodexExecutionResult(args=("codex", "--version"), returncode=0, stdout="ok", stderr="")
    payload = serialize_result(result)

    assert "\"--version\"" in payload


def test_sanitize_environment_strips_virtualenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "value")
    env = sanitize_environment()
    assert "PYTHONPATH" not in env
    assert isinstance(env, dict)
