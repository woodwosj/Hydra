# Hydra MCP Tool Catalog

Hydra MCP exposes a suite of Model Context Protocol (MCP) tools for coordinating Codex
agents, persisting their context, and supervising multi-agent workflows. The call syntax in
this catalog matches the JSON payloads accepted by the MCP host (for example the Codex CLI
`hydra.<tool>` commands).

> **Tip**: Unless noted otherwise, every tool expects a JSON object. Even optional objects
> such as `inputs`, `metadata`, or `context_package` should be provided as `{}` when you do
> not have extra data.

---

## spawn_agent
- **Purpose**: Launch a new Codex CLI session using a configured Hydra profile.
- **Required fields**:
  - `profile_id` – Agent profile id (e.g., `generalist`, `code_reviewer`).
  - `task_brief` – Human-readable instructions for the agent.
  - `goalset` – Array of goals (use `[]` to defer to profile defaults).
  - `inputs` – Context payload object (use `{}` if no additional context).
- **Optional fields**: `flags`, `working_dir`, `task_id`.
- **Response**: `{ "session_id", "returncode", "output_preview" }`.
- **Command example**:
  ```
  hydra.spawn_agent({
    "profile_id": "generalist",
    "task_brief": "Investigate Odoo v19 changes versus v18 using Context7.",
    "goalset": [
      "Collect authoritative release notes",
      "Summarize functional, UI, and backend changes"
    ],
    "inputs": {
      "notes": "Prioritize official documentation and trusted blogs.",
      "tools": ["context7", "jina"],
      "deliverables": ["summary", "source_table"]
    },
    "flags": ["--model", "gpt-5-codex"],
    "task_id": "odoo-release-research"
  })
  ```
- **Typical use cases**: Delegating implementation work, launching ad-hoc research, or
  requesting a reviewer pass.

## list_agents
- **Purpose**: Enumerate Hydra agent profiles with persona metadata.
- **Arguments**: none.
- **Response**: Array of `{id, title, persona, goalset, constraints, tags}`.
- **Command example**:
  ```
  hydra.list_agents({})
  ```
- **Typical use cases**: Host UI profile selection, validating profile availability before
  delegating work.

## summarize_session
- **Purpose**: Condense a persisted session timeline from Chroma.
- **Required fields**: `session_id`.
- **Optional fields**: `detail_level` (`"brief"` | `"full"`, default `"brief"`).
- **Response**: `{ "session_id", "event_count", "timeline" or "timeline_preview" }`.
- **Command example**:
  ```
  hydra.summarize_session({
    "session_id": "generalist-20251001-abc123",
    "detail_level": "brief"
  })
  ```
- **Typical use cases**: Reviewer preparation, audit logs, status dashboards.

## log_context
- **Purpose**: Persist ad-hoc notes, references, or attachments to Chroma.
- **Required fields**: `session_id`, `title`, `notes`.
- **Optional fields**: `tags`, `metadata`.
- **Response**: `{ "event_id", "timestamp" }`.
- **Command example**:
  ```
  hydra.log_context({
    "session_id": "generalist-20250924-ff0042",
    "title": "API quota guidance",
    "notes": "Use staging keys after 18:00 UTC to avoid throttling.",
    "tags": ["api", "quota"],
    "metadata": {
      "source": "support-ticket-4821",
      "owner": "Conport"
    }
  })
  ```
- **Typical use cases**: Conport manager compiling research packets, reviewer attaching
  audit annotations.

## query_context
- **Purpose**: Perform keyword/metadata search over stored session history.
- **Required fields**: `query`.
- **Optional fields**: `session_id`, `limit`, `filters`.
- **Response**: `{ "matches": [ {"event_id", "event_type", "excerpt", ...} ] }`.
- **Command example**:
  ```
  hydra.query_context({
    "query": "httpx timeout",
    "session_id": "generalist-20250924-ff0042",
    "limit": 5,
    "filters": {"event_type": "context_note"}
  })
  ```
- **Typical use cases**: Troubleshooting regressions, retrieving prior art for reviewers.

## export_session
- **Purpose**: Produce a portable session bundle.
- **Required fields**: `session_id`.
- **Optional fields**: `format` (`"json"` | `"markdown"`, default `"json"`).
- **Response**: `{ "format", "session_id", "data" }`.
- **Command example**:
  ```
  hydra.export_session({
    "session_id": "code_reviewer-20250925-e1f2ab",
    "format": "markdown"
  })
  ```
- **Typical use cases**: Sharing progress externally, archiving sessions for compliance.

## terminate_session
- **Purpose**: Stop a running Codex session and log the reason.
- **Required fields**: `session_id`.
- **Optional fields**: `reason`.
- **Response**: `{ "session_id", "reason", "event_id" }`.
- **Command example**:
  ```
  hydra.terminate_session({
    "session_id": "generalist-20250924-ff0042",
    "reason": "Superseded by newer context package"
  })
  ```
- **Typical use cases**: Emergency stop for unsafe work, reclaiming resources from stale
  sessions.

## create_task
- **Purpose**: Register a Hydra task with optional context packaging.
- **Required fields**: `profile_id`, `task_brief`.
- **Optional fields**: `context_package`, `metadata`.
- **Response**: `{ "task_id", "profile_id", "status", ... }`.
- **Command example**:
  ```
  hydra.create_task({
    "profile_id": "generalist",
    "task_brief": "Implement Odoo v19 release-notes landing page.",
    "context_package": {
      "worktree_path": "/repos/odoo-site",
      "worktree_branch": "feature/v19-notes",
      "files": ["docs/releases/v19.md"],
      "research_refs": ["https://odoo.com/releases/v19"]
    },
    "metadata": {
      "priority": "P1",
      "ticket": "OD-3421"
    }
  })
  ```
- **Typical use cases**: Conport manager tracking multi-step efforts, CI pipelines staging
  worktrees before agent activation.

## start_task
- **Purpose**: Spawn the agent associated with a task created via `create_task`.
- **Required fields**: `task_id`.
- **Response**: `{ "task": {...}, "spawn_result": {...} }`.
- **Command example**:
  ```
  hydra.start_task({
    "task_id": "odoo-release-research"
  })
  ```
- **Typical use cases**: Just-in-time activation once prep work is complete.

## task_status
- **Purpose**: Fetch the current status snapshot for a Hydra task.
- **Required fields**: `task_id`.
- **Response**: `{ "task_id", "status", "session_id", ... }`.
- **Command example**:
  ```
  hydra.task_status({
    "task_id": "odoo-release-research"
  })
  ```
- **Typical use cases**: Dashboards, orchestration scripts checking for completion or
  failure.

## complete_task
- **Purpose**: Mark a task outcome and capture closing notes.
- **Required fields**: `task_id`.
- **Optional fields**: `outcome` (default `"completed"`), `summary`.
- **Response**: Updated task summary.
- **Command example**:
  ```
  hydra.complete_task({
    "task_id": "odoo-release-research",
    "outcome": "completed",
    "summary": "Release highlights drafted and shared with marketing."
  })
  ```
- **Typical use cases**: Reviewer sign-off, automation that records failure notes before
  retries.

---

### Resume alert utilities
- Inspect alert history:
  ```bash
  PYTHONPATH=src python scripts/hydra_diag.py alerts --limit 5
  ```
- Forward alert payloads:
  ```bash
  PYTHONPATH=src python scripts/hydra_alert_forwarder.py --format text --limit 5
  ```
- See `docs/resume_alert_monitoring.md` for deeper monitoring integrations.

---

All tools return structured JSON responses aligned with MCP schemas. Surface these
descriptions verbatim in host annotations so operators and downstream agents can reason
about the available capabilities.
