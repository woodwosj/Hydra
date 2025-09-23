"""Async runner for the Codex CLI."""

from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .utils import sanitize_environment


class CodexRunnerError(RuntimeError):
    """Base class for Codex runner errors."""


class CodexNotFoundError(CodexRunnerError):
    """Raised when the Codex CLI executable cannot be located."""


@dataclass(slots=True)
class CodexExecutionResult:
    """Holds the outcome of a Codex CLI invocation."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CodexRunner:
    """Execute Codex CLI commands asynchronously."""

    def __init__(self, executable: Path | None = None) -> None:
        self._executable_path = self._resolve_executable(executable)

    @staticmethod
    def _resolve_executable(explicit: Path | None) -> Path:
        if explicit is not None:
            candidate = Path(explicit)
            if candidate.exists() and candidate.is_file():
                return candidate
            raise CodexNotFoundError(f"Codex executable not found at {candidate}")

        binary = shutil.which("codex")
        if binary is None:
            raise CodexNotFoundError("Codex CLI executable not found on PATH")
        return Path(binary)

    @property
    def executable(self) -> Path:
        return self._executable_path

    async def version(self) -> CodexExecutionResult:
        return await self._invoke("--version")

    async def spawn(self, command: str, *, flags: Sequence[str] | None = None) -> CodexExecutionResult:
        args: list[str] = ["exec", command]
        prefix = list(flags or [])
        return await self._invoke(*prefix, *args)

    async def resume(self, session_id: str, *, flags: Sequence[str] | None = None) -> CodexExecutionResult:
        args: list[str] = ["resume", session_id]
        prefix = list(flags or [])
        return await self._invoke(*prefix, *args)

    async def _invoke(self, *args: str) -> CodexExecutionResult:
        cmd = [str(self._executable_path), *args]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=sanitize_environment(),
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return CodexExecutionResult(args=tuple(cmd), returncode=process.returncode, stdout=stdout, stderr=stderr)


class FakeCodexRunner(CodexRunner):
    """Test double that simulates Codex CLI responses."""

    def __init__(self, responses: Iterable[CodexExecutionResult] | None = None) -> None:  # type: ignore[override]
        self._responses = list(responses or [])
        self._invocations: list[tuple[str, ...]] = []
        self._executable_path = Path("/tmp/fake-codex")

    async def _invoke(self, *args: str) -> CodexExecutionResult:  # type: ignore[override]
        self._invocations.append(tuple(args))
        if self._responses:
            return self._responses.pop(0)
        return CodexExecutionResult(args=tuple(args), returncode=0, stdout="", stderr="")

    @property
    def invocations(self) -> list[tuple[str, ...]]:
        return self._invocations


def serialize_result(result: CodexExecutionResult) -> str:
    """Serialize a command result for storage in the context log."""

    return json.dumps(
        {
            "args": list(result.args),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )

