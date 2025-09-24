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
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}")
        raise SystemExit(1)

    status_counts: dict[str, int] = {}
    for task in tasks:
        status = task.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    metrics = {
        "tasks_total": len(tasks),
        "status_counts": status_counts,
        "worktrees_total": len(worktrees),
        "sessions_total": len(sessions),
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
