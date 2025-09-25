"""Forward persisted resume alerts to monitoring-friendly output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from hydra_mcp.config import HydraSettings
from hydra_mcp.storage import ChromaStore, ChromaUnavailableError, ChromaEvent


def load_store(settings: HydraSettings) -> ChromaStore:
    """Construct a ChromaStore using the provided settings."""

    return ChromaStore(settings.chroma_persist_path)


def _normalize_events(
    events: Iterable[ChromaEvent],
    *,
    task_id: str | None = None,
) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for event in events:
        if task_id and event.metadata.get("task_id") != task_id:
            continue
        filtered.append(
            {
                "event_id": event.id,
                "task_id": event.metadata.get("task_id"),
                "session_id": event.metadata.get("session_id"),
                "failure_count": event.metadata.get("failure_count"),
                "threshold": event.metadata.get("threshold"),
                "resume_status": event.metadata.get("resume_status"),
                "timestamp": event.timestamp.isoformat(),
            }
        )
    filtered.sort(key=lambda item: item["timestamp"])
    return filtered


def _default_event_formatter(item: dict[str, object]) -> str:
    return " | ".join(
        [
            f"task={item['task_id']}",
            f"session={item['session_id']}",
            f"failures={item['failure_count']}",
            f"threshold={item['threshold']}",
            f"status={item['resume_status']}",
            f"timestamp={item['timestamp']}",
        ]
    )


def forward_alerts(args: argparse.Namespace, *, formatter=_default_event_formatter) -> int:
    settings = HydraSettings()
    try:
        store = load_store(settings)
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}", file=sys.stderr)
        return 1

    try:
        alerts = store.search_events(filters={"event_type": "resume_alert"})
    except ChromaUnavailableError as exc:
        print(f"Chroma unavailable: {exc}", file=sys.stderr)
        return 1

    payload = _normalize_events(alerts, task_id=args.task_id)
    if args.limit is not None and args.limit > 0:
        payload = payload[-args.limit :]
    if args.format == "json":
        output_text = json.dumps(payload, indent=2)
    else:
        output_text = "\n".join(formatter(item) for item in payload)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_text, encoding="utf-8")
    else:
        print(output_text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forward resume alert events to stdout or a file for monitoring integrations."
    )
    parser.add_argument("--task-id", help="Filter resume alerts by task id", default=None)
    parser.add_argument(
        "--format",
        choices={"json", "text"},
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument("--output", help="Optional path to write the alert payload to")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="If provided, emit only the latest N alerts after filtering",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    exit_code = forward_alerts(args)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
