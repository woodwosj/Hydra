"""Tool registration for Hydra MCP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal
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
    query_context: Any
    terminate_session: Any
    export_session: Any
    create_task: Any
    start_task: Any
    task_status: Any
    complete_task: Any
    tasks_state: dict[str, dict[str, Any]]


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

    tasks_state: dict[str, dict[str, Any]] = {}
    TASK_STATUSES = {"pending", "running", "completed", "cancelled", "failed"}

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

    async def _terminate_session(
        session_id: str,
        reason: str | None = None,
        context: Context | None = None,
    ) -> dict[str, Any]:
        """Record a termination event for a session."""

        event_id = None
        if chroma_store is not None:
            event = chroma_store.record_event(
                session_id=session_id,
                event_type="terminate_session",
                body={"reason": reason},
                metadata={"reason": reason or "unspecified"},
            )
            event_id = event.id
        if context is not None:
            context.logger.warning(
                "Termination requested",
                extra={"session_id": session_id, "reason": reason},
            )
        return {"session_id": session_id, "reason": reason, "event_id": event_id}

    def _query_context(
        query: str,
        *,
        session_id: str | None = None,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        context: Context | None = None,
    ) -> dict[str, Any]:
        """Search stored events by keyword."""

        store = _require_chroma()
        effective_filters = filters.copy() if filters else {}
        if session_id:
            effective_filters["session_id"] = session_id
        matches = store.search_events(query, filters=effective_filters or None, limit=limit)
        payload = [
            {
                "event_id": event.id,
                "session_id": event.session_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "metadata": event.metadata,
                "excerpt": event.document[:200],
            }
            for event in matches
        ]
        if context is not None:
            context.logger.debug(
                "Query context",
                extra={"query": query, "results": len(payload)},
            )
        return {"matches": payload}

    def _export_session(
        session_id: str,
        *,
        format: Literal["json", "markdown"] = "json",
        context: Context | None = None,
    ) -> dict[str, Any]:
        """Export a session timeline in the requested format."""

        store = _require_chroma()
        events = store.fetch_session_events(session_id)
        if format == "json":
            data = [
                {
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp.isoformat(),
                    "document": event.document,
                    "metadata": event.metadata,
                }
                for event in events
            ]
            payload = {"format": "json", "session_id": session_id, "data": data}
        elif format == "markdown":
            lines = [f"# Session {session_id}"]
            for event in events:
                lines.append(
                    f"- {event.timestamp.isoformat()} [{event.event_type}] {event.document[:200]}"
                )
            payload = {"format": "markdown", "session_id": session_id, "data": "\n".join(lines)}
        else:
            raise ValueError("Unsupported export format. Use 'json' or 'markdown'.")

        if context is not None:
            context.logger.info(
                "Exported session",
                extra={"session_id": session_id, "format": format},
            )
        return payload

    tool_query = server.tool(
        name="query_context",
        description="Search stored context and events using a keyword filter.",
    )(_query_context)

    tool_terminate = server.tool(
        name="terminate_session",
        description="Record a termination request for a session and log the reason.",
    )(_terminate_session)

    tool_export = server.tool(
        name="export_session",
        description="Export a session timeline as JSON or Markdown.",
    )(_export_session)

    def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
        return {
            "task_id": task["task_id"],
            "profile_id": task["profile_id"],
            "status": task["status"],
            "created_at": task["created_at"],
            "updated_at": task["updated_at"],
            "session_id": task.get("session_id"),
            "task_brief": task["task_brief"],
            "metadata": task.get("metadata", {}),
        }

    def _record_task_event(task_id: str, event_type: str, payload: dict[str, Any]) -> None:
        if chroma_store is None:
            return
        chroma_store.record_event(
            session_id=f"task::{task_id}",
            event_type=event_type,
            body=payload,
            metadata={
                "task_id": task_id,
                "status": payload.get("status"),
                "event_type": event_type,
            },
        )

    def _create_task(
        profile_id: str,
        task_brief: str,
        *,
        context_package: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        context: Context | None = None,
    ) -> dict[str, Any]:
        profile_map = profiles.load_all()
        if profile_id not in profile_map:
            raise ValueError(f"Unknown profile '{profile_id}'")

        task_id = uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        task = {
            "task_id": task_id,
            "profile_id": profile_id,
            "task_brief": task_brief,
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp,
            "session_id": None,
            "context_package": context_package or {},
            "metadata": metadata or {},
        }
        tasks_state[task_id] = task

        _record_task_event(task_id, "task_created", {"status": "pending", "task_brief": task_brief})

        if context is not None:
            context.logger.info("Created task", extra={"task_id": task_id, "profile_id": profile_id})

        return _task_summary(task)

    async def _start_task(
        task_id: str,
        *,
        flags: list[str] | None = None,
        context: Context | None = None,
    ) -> dict[str, Any]:
        if task_id not in tasks_state:
            raise ValueError(f"Task '{task_id}' not found")
        task = tasks_state[task_id]
        if task["status"] not in {"pending", "queued"}:
            raise ValueError(f"Task '{task_id}' is not in a startable state (current: {task['status']})")

        result = await _spawn_agent(
            profile_id=task["profile_id"],
            task_brief=task["task_brief"],
            goalset=None,
            inputs=task.get("context_package"),
            flags=flags,
            context=context,
        )

        task["status"] = "running"
        task["session_id"] = result["session_id"]
        task["updated_at"] = datetime.now(timezone.utc).isoformat()

        _record_task_event(
            task_id,
            "task_started",
            {"status": "running", "session_id": task["session_id"], "flags": flags or []},
        )

        return {
            "task": _task_summary(task),
            "spawn_result": result,
        }

    def _task_status(task_id: str, context: Context | None = None) -> dict[str, Any]:
        if task_id not in tasks_state:
            raise ValueError(f"Task '{task_id}' not found")
        task = tasks_state[task_id]
        if context is not None:
            context.logger.debug("Task status", extra={"task_id": task_id, "status": task["status"]})
        return _task_summary(task)

    def _complete_task(
        task_id: str,
        *,
        outcome: str = "completed",
        summary: str | None = None,
        context: Context | None = None,
    ) -> dict[str, Any]:
        if task_id not in tasks_state:
            raise ValueError(f"Task '{task_id}' not found")
        outcome_lower = outcome.lower()
        if outcome_lower not in TASK_STATUSES:
            raise ValueError(f"Invalid outcome '{outcome}'. Must be one of {sorted(TASK_STATUSES)}")

        task = tasks_state[task_id]
        task["status"] = outcome_lower
        task["updated_at"] = datetime.now(timezone.utc).isoformat()
        if summary:
            task.setdefault("metadata", {})["summary"] = summary

        _record_task_event(
            task_id,
            "task_completed",
            {"status": outcome_lower, "summary": summary},
        )

        if context is not None:
            context.logger.info(
                "Task completed",
                extra={"task_id": task_id, "status": outcome_lower},
            )

        return _task_summary(task)

    tool_create_task = server.tool(
        name="create_task",
        description="Create a task for the multi-agent workflow and store context metadata.",
    )(_create_task)

    tool_start_task = server.tool(
        name="start_task",
        description="Start a pending task by spawning the associated agent profile.",
    )(_start_task)

    tool_task_status = server.tool(
        name="task_status",
        description="Fetch the latest status for a Hydra-managed task.",
    )(_task_status)

    tool_complete_task = server.tool(
        name="complete_task",
        description="Mark a task as completed, cancelled, or failed and store summary notes.",
    )(_complete_task)

    return ToolHandles(
        spawn_agent=tool_spawn,
        list_agents=tool_list,
        summarize_session=tool_summarize,
        log_context=tool_log,
        query_context=tool_query,
        terminate_session=tool_terminate,
        export_session=tool_export,
        create_task=tool_create_task,
        start_task=tool_start_task,
        task_status=tool_task_status,
        complete_task=tool_complete_task,
        tasks_state=tasks_state,
    )


__all__ = ["register_tools", "ToolHandles"]
