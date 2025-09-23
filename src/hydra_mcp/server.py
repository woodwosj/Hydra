"""FastMCP server bootstrap for Hydra."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastmcp import Context, FastMCP

from . import __version__
from .config import HydraSettings, get_settings


def configure_logging(level: str) -> None:
    """Configure root logging for the Hydra server."""

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )


def create_server(settings: Optional[HydraSettings] = None) -> FastMCP:
    """Instantiate the FastMCP server with baseline resources."""

    settings = settings or get_settings()

    server = FastMCP(
        name="Hydra MCP",
        version=__version__,
        instructions=(
            "Hydra orchestrates specialized Codex agents with persistent context "
            "storage in Chroma. Use provided tools to spawn, observe, and summarize "
            "agent activity."
        ),
    )

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

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_version": __version__,
            "log_level": settings.log_level,
            "chroma_path": str(settings.chroma_persist_path),
            "codex_path": settings.codex_path,
            "codex_default_model": settings.codex_default_model,
            "request_id": getattr(context, "request_id", None),
        }
        return json.dumps(payload)

    return server


def main() -> None:
    """Entry point for running the Hydra MCP server via CLI."""

    settings = get_settings()
    configure_logging(settings.log_level)

    server = create_server(settings)
    logging.getLogger(__name__).info("Launching Hydra MCP server", extra={
        "version": __version__,
        "log_level": settings.log_level,
        "chroma_path": str(settings.chroma_persist_path),
    })
    server.run()


if __name__ == "__main__":
    main()
