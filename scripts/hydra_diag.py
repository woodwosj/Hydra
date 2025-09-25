"""Hydra MCP diagnostics CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hydra_mcp.config import HydraSettings
from hydra_mcp.storage import ChromaStore, ChromaUnavailableError


def load_store(settings: HydraSettings) -> ChromaStore:
    try:
        return ChromaStore(settings.chroma_persist_path)
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}")
        raise SystemExit(1)


def cmd_tasks(args: argparse.Namespace) -> None:
    settings = HydraSettings()
    store = load_store(settings)
    try:
        tasks = store.replay_tasks()
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}")
        raise SystemExit(1)
    if args.json:
        print(json.dumps(tasks, indent=2))
    else:
        for task in tasks:
            print(f"{task['task_id']} [{task['status']}] -> {task.get('session_id')}")


def cmd_worktrees(args: argparse.Namespace) -> None:
    settings = HydraSettings()
    store = load_store(settings)
    try:
        records = store.list_worktrees(task_id=args.task_id)
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}")
        raise SystemExit(1)
    print(json.dumps([record.__dict__ for record in records], indent=2))




def cmd_metrics(args: argparse.Namespace) -> None:
    settings = HydraSettings()
    store = load_store(settings)
    try:
        tasks = store.replay_tasks()
        worktrees = store.list_worktrees()
        sessions = store.list_session_tracking()
        resume_events = store.search_events(filters={"event_type": "task_resume"})
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}")
        raise SystemExit(1)

    status_counts: dict[str, int] = {}
    for task in tasks:
        status = task.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    resume_counts: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    failure_statuses = {"resume_failed", "resume_error"}
    for event in resume_events:
        status = event.metadata.get("resume_status") or event.metadata.get("status") or "unknown"
        resume_counts[status] = resume_counts.get(status, 0) + 1
        if status in failure_statuses:
            task_id = event.metadata.get("task_id")
            if task_id:
                failure_counts[task_id] = failure_counts.get(task_id, 0) + 1

    alert_threshold = settings.resume_alert_threshold
    resume_alerts = [
        {"task_id": task_id, "failure_count": count}
        for task_id, count in failure_counts.items()
        if count >= alert_threshold
    ]

    metrics = {
        "tasks_total": len(tasks),
        "status_counts": status_counts,
        "worktrees_total": len(worktrees),
        "sessions_total": len(sessions),
        "resume_attempts": len(resume_events),
        "resume_status_counts": resume_counts,
        "resume_alert_threshold": alert_threshold,
        "resume_failure_alerts": resume_alerts,
    }

    print(json.dumps(metrics, indent=2))


def cmd_sessions(args: argparse.Namespace) -> None:
    settings = HydraSettings()
    store = load_store(settings)
    try:
        records = store.list_session_tracking(task_id=args.task_id)
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}")
        raise SystemExit(1)
    print(json.dumps([record.__dict__ for record in records], indent=2))


def cmd_alerts(args: argparse.Namespace) -> None:
    settings = HydraSettings()
    store = load_store(settings)
    try:
        alerts = store.search_events(filters={"event_type": "resume_alert"})
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}")
        raise SystemExit(1)

    task_id = args.task_id
    if task_id:
        alerts = [event for event in alerts if event.metadata.get("task_id") == task_id]

    alerts.sort(key=lambda event: event.timestamp)
    if args.limit is not None and args.limit > 0:
        alerts = alerts[-args.limit :]

    payload = [
        {
            "event_id": getattr(event, "id", None),
            "task_id": event.metadata.get("task_id"),
            "session_id": event.metadata.get("session_id"),
            "failure_count": event.metadata.get("failure_count"),
            "threshold": event.metadata.get("threshold"),
            "resume_status": event.metadata.get("resume_status"),
            "timestamp": event.timestamp.isoformat(),
        }
        for event in alerts
    ]
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hydra MCP diagnostics")
    sub = parser.add_subparsers(dest="cmd")

    p_tasks = sub.add_parser("tasks", help="List replayed tasks")
    p_tasks.add_argument("--json", action="store_true", help="Output JSON")
    p_tasks.set_defaults(func=cmd_tasks)

    p_worktrees = sub.add_parser("worktrees", help="List worktree records")
    p_worktrees.add_argument("--task-id")
    p_worktrees.set_defaults(func=cmd_worktrees)

    p_sessions = sub.add_parser("sessions", help="List session tracking records")
    p_sessions.add_argument("--task-id")
    p_sessions.set_defaults(func=cmd_sessions)

    p_metrics = sub.add_parser("metrics", help="Show task/worktree/session counts")
    p_metrics.set_defaults(func=cmd_metrics)

    p_alerts = sub.add_parser(
        "alerts",
        help="List resume alert events (failure threshold breaches)",
    )
    p_alerts.add_argument("--task-id")
    p_alerts.add_argument(
        "--limit",
        type=int,
        default=None,
        help="If provided, show only the latest N alerts",
    )
    p_alerts.set_defaults(func=cmd_alerts)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
