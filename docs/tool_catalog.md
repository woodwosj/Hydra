# Hydra MCP Tool Catalog

Hydra exposes a suite of MCP tools designed to coordinate multi-agent development flows.
Each entry below provides the formal description returned to hosts, example host-side
prompts, and typical usage patterns.

## spawn_agent
- **Purpose**: Launch a new Codex CLI session with the specified agent profile and goal.
- **Arguments**:
  - `profile_id` *(string, required)* – Agent profile key (e.g., `generalist`, `code_reviewer`).
  - `task_brief` *(string, required)* – Human-readable brief delivered to the agent.
  - `inputs` *(object, optional)* – Structured context payload (file highlights, diffs, links).
  - `goalset` *(array[string], optional)* – Overrides default profile goals for this run.
  - `working_dir` *(string, optional)* – Target repository path/worktree.
  - `flags` *(array[string], optional)* – Additional Codex CLI flags (e.g., `--model`).
- **Response**: Session identifier plus first log entries captured from Codex.
- **Example prompt**: `Hydra, spawn a generalist agent to draft the multi-agent workflow
document using the research pack from Conport.`
- **Typical use cases**:
  - Conport manager delegating implementation work to the coder agent.
  - Coder agent requesting a reviewer run with additional verification context.

## list_agents
- **Purpose**: Enumerate available agent profiles with metadata.
- **Response**: Array of `{id, title, persona, tags, default_goalset}` records.
- **Example prompt**: `List the available Hydra agent profiles and their specialities.`
- **Typical use cases**:
  - Host UI rendering selectable agent personas.
  - Automated workflows validating profile availability before delegation.

## summarize_session
- **Purpose**: Condense a session timeline from Chroma into a structured summary.
- **Arguments**: `session_id` *(string, required)*, `detail_level` *(enum: brief|full)*.
- **Response**: JSON summary including checklist completion, major actions, open risks.
- **Example prompt**: `Summarize session hydra-2025-002 with a focus on outstanding TODOs.`
- **Alerts**: Use `hydra_diag alerts --task-id task-123 --limit 5` to list the latest resume alert events (failures that hit alert thresholds) for a specific task; omit `--task-id` to review all alerts. Combine with `metrics` for aggregate counts. See `docs/resume_alert_monitoring.md` for forwarder and validation workflow.
- **Forward Alerts**: Run `python scripts/hydra_alert_forwarder.py --format text --limit 5 --output alerts.log` to emit the latest alert summaries to a log/file for downstream monitoring jobs.
- **Typical use cases**:
  - Reviewer agent gathering context prior to assessment.
  - Managers compiling daily reports of active efforts.

## terminate_session
- **Purpose**: Stop a running Codex session and mark it as cancelled.
- **Arguments**: `session_id` *(string, required)*, `reason` *(string, optional)*.
- **Response**: Confirmation plus last-known session status.
- **Example prompt**: `Terminate the stalled hydra-2025-001 session; include reason
"blocked on API quota".`
- **Typical use cases**:
  - Conport manager reclaiming resources from stuck agents.
  - Emergency stop when unsafe actions are detected.

## log_context
- **Purpose**: Persist ad-hoc notes, references, or attachments into Chroma.
- **Arguments**: `session_id` *(string, required)*, `title`, `notes`, `tags`, `attachments`.
- **Response**: Event record identifier.
- **Example prompt**: `Attach these API docs snippets to the reviewer session for quick
reference.`
- **Typical use cases**:
  - Conport manager compiling research packets for downstream agents.
  - Reviewer appending audit notes or linking to external tickets.

## query_context
- **Purpose**: Semantic search over stored session history and knowledge capsules.
- **Arguments**: `query` *(string, required)*, `filters` *(object, optional)*,
  `limit` *(integer, optional)*.
- **Response**: Ranked list of context fragments with metadata and similarity score.
- **Example prompt**: `Find past fixes related to "httpx timeout" across Hydra sessions.`
- **Typical use cases**:
  - Troubleshooting regression categories using historical solutions.
  - Reviewer verifying whether similar issues were addressed previously.

## export_session
- **Purpose**: Produce a portable bundle of session transcripts, diffs, and metadata.
- **Arguments**: `session_id`, `format` *(enum: json|markdown|zip)*.
- **Response**: Download link or inline data blob.
- **Example prompt**: `Export the reviewer session as markdown for sharing in Slack.`
- **Typical use cases**:
  - Sharing progress with stakeholders outside MCP hosts.
  - Archiving completed efforts for compliance reviews.

---

All tools return structured JSON responses aligned with MCP schemas. Descriptions and
usage notes should be surfaced verbatim in tool annotations to aid host-side UX and model
reasoning.
