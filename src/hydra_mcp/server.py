"""FastMCP server bootstrap for Hydra."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastmcp import Context, FastMCP

from . import __version__
from .codex import CodexNotFoundError, CodexRunner
from .config import HydraSettings, get_settings
from .profiles import ProfileLoadError, ProfileLoader
from .storage import ChromaStore, ChromaUnavailableError
from .tools import register_tools


def configure_logging(level: str) -> None:
    """Configure root logging for the Hydra server."""

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )


def _run_sync(coro):
    """Execute an async coroutine on a dedicated event loop."""

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def create_server(settings: Optional[HydraSettings] = None) -> FastMCP:
    """Instantiate the FastMCP server with baseline resources."""

    settings = settings or get_settings()

    profile_loader = ProfileLoader(settings.profile_paths)

    codex_runner: CodexRunner | None = None
    codex_metadata = {
        "available": False,
        "version": None,
        "error": None,
    }

    try:
        codex_runner = CodexRunner(Path(settings.codex_path) if settings.codex_path else None)
        codex_metadata["available"] = True
        version_result = _run_sync(codex_runner.version())
        if version_result.ok:
            codex_metadata["version"] = version_result.stdout.strip()
        else:
            codex_metadata["error"] = (
                version_result.stderr.strip()
                or "Codex version command failed with exit code"
            )
    except CodexNotFoundError as exc:
        codex_metadata["error"] = str(exc)
        codex_runner = None

    chroma_store: ChromaStore | None = None
    chroma_metadata = {
        "available": False,
        "path": str(settings.chroma_persist_path),
        "collection": "hydra_runs",
        "error": None,
    }

    try:
        chroma_store = ChromaStore(settings.chroma_persist_path)
        chroma_store.ping()
        chroma_metadata["available"] = True
    except ChromaUnavailableError as exc:
        chroma_metadata["error"] = str(exc)
        chroma_store = None

    server = FastMCP(
        name="Hydra MCP",
        version=__version__,
        instructions=(
            "Hydra orchestrates specialized Codex agents with persistent context "
            "storage in Chroma. Use provided tools to spawn, observe, and summarize "
            "agent activity."
        ),
    )

    handles = register_tools(
        server,
        profiles=profile_loader,
        settings=settings,
        codex_runner=codex_runner,
        chroma_store=chroma_store,
    )

    tasks_state = handles.tasks_state
    session_state = getattr(handles, "session_state", {})
    worktree_state = getattr(handles, "worktree_state", {})

    @server.resource(
        "resource://hydra/status",
        name="hydra_status",
        title="Hydra MCP Status",
        description="Provides the current runtime status for the Hydra MCP server.",
        mime_type="application/json",
        tags={"status", "health"},
    )
    def status_resource(context: Context) -> str:
        """Return a JSON string summarizing basic runtime state."""

        try:
            profiles = profile_loader.load_all()
            profile_ids = sorted(profiles.keys())
            profile_error: str | None = None
        except ProfileLoadError as exc:
            profile_ids = []
            profile_error = str(exc)

        status_counts: dict[str, int] = {}
        for task in tasks_state.values():
            status = task.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        worktree_summary = []
        session_summary = []
        storage_error = None
        if chroma_store is not None:
            try:
                recent_worktrees = chroma_store.list_worktrees()
                worktree_summary = [
                    {
                        "task_id": record.task_id,
                        "path": record.path,
                        "status": record.status,
                    }
                    for record in recent_worktrees[-5:]
                ]
                recent_sessions = chroma_store.list_session_tracking()
                session_summary = [
                    {
                        "session_id": record.session_id,
                        "profile_id": record.profile_id,
                        "status": record.status,
                    }
                    for record in recent_sessions[-5:]
                ]
            except Exception as exc:  # defensive: avoid status failure
                storage_error = str(exc)

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_version": __version__,
            "log_level": settings.log_level,
            "profiles": {
                "count": len(profile_ids),
                "ids": profile_ids,
                "error": profile_error,
            },
            "codex": {
                "path": settings.codex_path,
                "default_model": settings.codex_default_model,
                **codex_metadata,
            },
            "storage": {
                "chroma": chroma_metadata,
                "worktrees_preview": worktree_summary,
                "sessions_preview": session_summary,
                "error": storage_error,
            },
            "tasks": {
                "count": len(tasks_state),
                "status_counts": status_counts,
                "sessions": list(session_state.values())[-5:],
                "worktrees": list(worktree_state.values())[-5:],
            },
            "request_id": getattr(context, "request_id", None),
        }
        return json.dumps(payload)

    setattr(server, "profile_loader", profile_loader)
    setattr(server, "codex_runner", codex_runner)
    setattr(server, "codex_metadata", codex_metadata)
    setattr(server, "chroma_store", chroma_store)
    setattr(server, "chroma_metadata", chroma_metadata)
    setattr(server, "tool_handles", handles)
    setattr(server, "tasks_state", tasks_state)
    return server


def main() -> None:
    """Entry point for running the Hydra MCP server via CLI."""

    settings = get_settings()
    configure_logging(settings.log_level)

    server = create_server(settings)
    logging.getLogger(__name__).info(
        "Launching Hydra MCP server",
        extra={
            "version": __version__,
            "log_level": settings.log_level,
            "codex_available": getattr(server, "codex_metadata", {}).get("available"),
            "chroma_available": getattr(server, "chroma_metadata", {}).get("available"),
        },
    )
    server.run()


if __name__ == "__main__":
    main()
