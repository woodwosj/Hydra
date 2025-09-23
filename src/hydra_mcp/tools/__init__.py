"""Tool registration for Hydra MCP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

try:
    from fastmcp import Context, FastMCP
except ImportError:  # pragma: no cover - fallback for limited test environments
    Context = FastMCP = object  # type: ignore[assignment]

from ..codex import CodexExecutionResult, CodexRunner
from ..config import HydraSettings
from ..profiles import AgentProfile, ProfileLoader
from ..storage import ChromaStore


@dataclass(slots=True)
class ToolHandles:
    spawn_agent: Any
    list_agents: Any
    summarize_session: Any
    log_context: Any


def _build_prompt(profile: AgentProfile, task_brief: str, goalset: Iterable[str] | None) -> str:
    goals = list(goalset) if goalset is not None else profile.goalset
    goal_text = "\n".join(f"- {goal}" for goal in goals)
    constraints = "\n".join(f"- {constraint}" for constraint in profile.constraints)
    checklist = "\n".join(f"- {item.description}" for item in profile.checklist_template)

    sections = [
        profile.system_prompt.strip(),
        "Task Brief:\n" + task_brief.strip(),
        "Goals:\n" + (goal_text or "- Follow the system prompt"),
    ]
    if constraints:
        sections.append("Constraints:\n" + constraints)
    if checklist:
        sections.append("Checklist Expectations:\n" + checklist)

    return "\n\n".join(sections)


def register_tools(
    server: FastMCP,
    *,
    profiles: ProfileLoader,
    settings: HydraSettings,
    codex_runner: CodexRunner | None,
    chroma_store: ChromaStore | None,
) -> ToolHandles:
    """Register Hydra's MCP tools on the server."""

    async def _spawn_agent(
        profile_id: str,
        task_brief: str,
        *,
        goalset: list[str] | None = None,
        inputs: dict[str, Any] | None = None,
        flags: list[str] | None = None,
        context: Context | None = None,
    ) -> dict[str, Any]:
        """Spawn a Codex agent session with the given profile and task brief."""

        if codex_runner is None:
            raise RuntimeError("Codex runner is unavailable; cannot spawn agent")

        profile_map = profiles.load_all()
        if profile_id not in profile_map:
            raise ValueError(f"Unknown profile '{profile_id}'")

        profile = profile_map[profile_id]
        prompt = _build_prompt(profile, task_brief, goalset)

        session_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        session_id = f"{profile.id}-{session_stamp}-{uuid4().hex[:6]}"

        command_flags: list[str] = []
        if settings.codex_default_model and not (flags and "--model" in flags):
            command_flags.extend(["--model", settings.codex_default_model])
        if flags:
            command_flags.extend(flags)

        result: CodexExecutionResult = await codex_runner.spawn(prompt, flags=command_flags)

        response = {
            "session_id": session_id,
            "profile": profile.id,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "flags": command_flags,
            "inputs": inputs or {},
        }

        if chroma_store is not None:
            chroma_store.record_event(
                session_id=session_id,
                event_type="spawn_agent",
                body=response,
                metadata={
                    "profile": profile.id,
                    "returncode": result.returncode,
                    "task_brief": task_brief[:2000],
                },
            )

        if context is not None:
            context.logger.info(
                "Spawned agent",
                extra={
                    "session_id": session_id,
                    "profile": profile.id,
                    "returncode": result.returncode,
                },
            )

        return {
            "session_id": session_id,
            "returncode": result.returncode,
            "output_preview": result.stdout[:2000],
        }

    def _list_agents(context: Context | None = None) -> list[dict[str, Any]]:
        """List available agent profiles."""

        profile_map = profiles.load_all()
        catalog = [
            {
                "id": profile.id,
                "title": profile.title,
                "persona": profile.persona,
                "goalset": profile.goalset,
                "constraints": profile.constraints,
                "tags": profile.metadata.get("tags", []),
            }
            for profile in profile_map.values()
        ]

        if context is not None:
            context.logger.debug("Listing Hydra agent profiles", extra={"count": len(catalog)})

        return catalog

    tool_spawn = server.tool(
        name="spawn_agent",
        description=(
            "Launch a Codex CLI agent using a Hydra profile. Provide a task brief, and "
            "optional goal overrides, inputs, and CLI flags. Returns a session id and "
            "execution summary."
        ),
        annotations={
            "safety": {
                "level": "caution",
                "notes": "Ensure task brief avoids destructive instructions before spawning",
            }
        },
    )(_spawn_agent)

    tool_list = server.tool(
        name="list_agents",
        description="List Hydra agent profiles with persona, goals, and constraints.",
    )(_list_agents)

    def _require_chroma() -> ChromaStore:
        if chroma_store is None:
            raise RuntimeError("Chroma store is unavailable; enable persistence before using this tool")
        return chroma_store

    def _summarize_session(
        session_id: str,
        detail_level: str = "brief",
        context: Context | None = None,
    ) -> dict[str, Any]:
        """Summarize stored events for a session."""

        store = _require_chroma()
        events = store.fetch_session_events(session_id)
        timeline = [
            {
                "sequence": event.metadata.get("sequence"),
                "event_type": event.event_type,
                "timestamp": event.metadata.get("timestamp"),
                "metadata": event.metadata,
            }
            for event in events
        ]
        summary = {
            "session_id": session_id,
            "event_count": len(events),
            "latest_event": timeline[-1] if timeline else None,
        }
        if detail_level == "full":
            summary["timeline"] = timeline
        else:
            summary["timeline_preview"] = timeline[:5]

        if context is not None:
            context.logger.debug(
                "Summarized session",
                extra={"session_id": session_id, "event_count": len(events)},
            )

        return summary

    def _log_context(
        session_id: str,
        title: str,
        notes: str,
        *,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        context: Context | None = None,
    ) -> dict[str, Any]:
        """Log a contextual note into the Chroma store."""

        store = _require_chroma()
        merged_meta = metadata.copy() if metadata else {}
        merged_meta.update({"title": title, "tags": tags or []})
        event = store.record_event(
            session_id=session_id,
            event_type="context_note",
            body={"title": title, "notes": notes, "tags": tags or []},
            metadata=merged_meta,
        )
        if context is not None:
            context.logger.info(
                "Logged context note",
                extra={"session_id": session_id, "event_id": event.id},
            )
        return {"event_id": event.id, "timestamp": event.timestamp.isoformat()}

    tool_summarize = server.tool(
        name="summarize_session",
        description="Summarize stored Hydra session events (set detail_level=full for entire timeline).",
    )(_summarize_session)

    tool_log = server.tool(
        name="log_context",
        description="Append a contextual note to a session, persisting to Chroma for downstream agents.",
    )(_log_context)

    return ToolHandles(
        spawn_agent=tool_spawn,
        list_agents=tool_list,
        summarize_session=tool_summarize,
        log_context=tool_log,
    )


__all__ = ["register_tools", "ToolHandles"]
