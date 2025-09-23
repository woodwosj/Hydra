# Hydra MCP Codex Implementation Plan

## 1. Objectives
- Deliver an MCP-compliant server (FastMCP 2.0) that Codex can call as a tool to spawn isolated Codex CLI sessions scoped by prompt/goalset.
- Provide a default general-purpose Hydra agent profile plus user-defined profiles (for example, a pre-wired code-reviewer) with reusable prompts and policies.
- Persist every agent run, decision, checklist, and artifact summary into ChromaDB with rich metadata for auditability and future retrieval.
- Keep Codex session orchestration and context storage independent of local git history so the MCP acts as a central record keeper.

## 2. Research Highlights
- **Codex CLI (docs/getting-started.md)**: use `codex` for interactive TUI, `codex "..."` to seed a prompt, and `codex exec "..."` for non-interactive automation; resume flows via `codex resume` and session IDs; key flags `--model` and `--ask-for-approval` noted for delegated runs.
- **FastMCP 2.0 (gofastmcp.com)**: Pythonic framework wrapping the official MCP SDK with decorators such as `@mcp.tool`; supports prompts/resources/tools, advanced patterns, and deployment helpers; docs are accessible via MCP server `https://gofastmcp.com/mcp`.
- **MCP specification (modelcontextprotocol)**: JSON-RPC 2.0 protocol between host, client, and server; servers expose resources, tools, and prompts; emphasises consent, safety, cancellation, and capability negotiation.
- **ChromaDB (github.com/chroma-core/chroma)**: embedding database with Python `chromadb.Client()`/`PersistentClient`; collections store `documents`, optional `embeddings`, and `metadatas` (arbitrary JSON) keyed by `ids`, enabling timestamped structured storage and semantic retrieval.

## 3. Architecture Blueprint
- **Hydra MCP Server**: FastMCP app exposing Codex orchestration tools/resources/prompts and handling authentication/policy guardrails.
- **Agent Profile Registry**: file- and DB-backed configuration describing default prompt, goalset, expected outputs, and checklist templates.
- **Codex Session Orchestrator**: wrapper around Codex CLI (`codex exec`, `codex resume`) running in headless mode, streaming progress, and capturing artifacts/logs.
- **Chroma Context Store**: persistent collection storing per-session events (documents) with metadata (agent id, timestamp, checklist state, related files) and embeddings for semantic lookup.
- **Observability & Control Plane**: structured logging, metrics hooks, cancellation/timeout manager, optional future multi-host deployment.

## 4. Implementation Phases
### Phase 0 – Foundations
1. Decide on runtime (Python 3.10+) and create a dedicated virtual environment.
2. Scaffold repo structure: `src/hydra_mcp/` package, `tests/`, `configs/`, `profiles/`, `scripts/`.
3. Initialize `pyproject.toml` with dependencies: `fastmcp`, `modelcontextprotocol`, `chromadb`, `pydantic`, `httpx`, `python-dotenv`, `typer`/`rich` for CLI, plus dev tools (`pytest`, `ruff`).
4. Establish `.env` schema for Codex binary path, default model, Chroma storage path.

### Phase 1 – FastMCP Server Skeleton
1. Implement `hydra_mcp/server.py` creating a `FastMCP("Hydra")` instance and wiring startup/shutdown hooks.
2. Define capability advertisement per MCP spec: declare support for tools, resources, prompts, plus optional sampling if future recursion is planned.
3. Expose a health resource (e.g., `GET /status`) using FastMCP utilities for remote monitoring.
4. Add CLI entry point (`python -m hydra_mcp.server`) for local runs and packaging.

### Phase 2 – Configuration & Agent Profiles
1. Design Pydantic models for prompts (`title`, `persona`, `system_prompt`, `goalset`, `constraints`, `checklist_template`).
2. Create default profile definitions in `profiles/default.yaml` (generalist) and `profiles/code_reviewer.yaml` mirroring the user example.
3. Implement a loader that merges base prompts, per-user overrides, and ad-hoc prompts supplied via MCP tool arguments.
4. Add validation and helpful error messages when a requested profile is missing or incomplete.

### Phase 3 – Codex Session Orchestrator
1. Detect Codex CLI availability and version at startup; expose as server capability metadata.
2. Wrap Codex execution in an async-friendly runner using `asyncio.create_subprocess_exec` so MCP tool calls do not block.
3. Support both "spawn new session" (via `codex exec` with constructed prompt) and "resume session" (via `codex resume <id>` when needed).
4. Capture stdout/stderr streams, exit codes, generated diff previews, and any approval prompts; normalize into structured event objects.
5. Create pluggable adapters so orchestration can be mocked in tests (e.g., using a fake Codex binary).

### Phase 4 – Chroma Persistence Layer
1. Initialize a persistent Chroma client (`chromadb.PersistentClient(path=...)`) with a dedicated collection (e.g., `hydra_runs`).
2. Define storage schema: each document stores JSON stringified summaries (`action`, `details`, `files`, `outcome`) with `metadatas` including `session_id`, `agent_profile`, `timestamp`, `tags`, `related_sessions`.
3. Embed textual summaries using Chroma’s default embeddings or a configured embedding function; ensure deterministic IDs (`f"{session_id}:{event_counter}"`).
4. Provide helper methods: `record_event`, `finalize_session`, `query_by_session`, `semantic_search(query, filters)`.
5. Add migration/maintenance utilities to vacuum old runs and export snapshots.

### Phase 5 – MCP Surface (Tools, Resources, Prompts)
1. **Tools**
   - `spawn_agent`: arguments (`profile_id`, `custom_prompt`, `goalset`, `inputs`, `working_dir`, `flags`); returns session identifier and initial log entries.
   - `list_agents`: returns available profiles with descriptions.
   - `summarize_session`: aggregates Chroma records into a high-level summary/checklist status.
   - `terminate_session`: sends cancel signal to orchestrator and records outcome.
   - `log_context`: optional manual notes appended by host/LLM into Chroma.
2. **Resources**
   - `hydra/profiles`: static resource exposing profile catalog.
   - `hydra/sessions/{id}`: dynamic resource delivering timeline + metadata for a session from Chroma.
   - `hydra/checklists/{id}`: surfaces checklist completion status.
3. **Prompts**
   - Export profile prompts via MCP prompt definitions to simplify host-side prompting.
   - Provide templated prompt for "additional agent" creation that host can reuse.
4. Adhere to MCP JSON schema expectations (use `fastmcp` models) and include human-readable descriptions for tool safety.

### Phase 6 – Multi-Agent Coordination Workflow
1. Implement an `AgentManager` coordinating spawned sessions, tracking lifecycle, and broadcasting state changes (queued → running → awaiting approval → completed/failed).
2. Support cascading delegation: allow one agent to request another profile via `spawn_agent` tool call with cross-linked metadata.
3. Encode business rules (e.g., code-reviewer must run before commit) in either server policy or host-accessible prompts.
4. Persist delegation graph in Chroma metadata (`parent_session_id`, `relationship`).
5. Provide optional scheduling/queuing to prevent race conditions on shared workspace.

### Phase 7 – Logging, Checklists, and Reporting
1. Define event types (command, diff, test, decision, approval) and ensure orchestrator emits them consistently.
2. Auto-populate checklist items from profile definitions and mark completion when matching events occur (e.g., `tests_passed` after seeing `npm test` success).
3. Generate periodic summaries (structured + narrative) and store them as dedicated Chroma documents for fast retrieval.
4. Expose summary data through MCP prompts/resources so hosts can request "latest status" quickly.

### Phase 8 – Security & Safety Controls
1. Follow MCP guidance: require explicit arguments for destructive operations, return preview-only diffs instead of auto-committing.
2. Implement allowlists/denylists for directories Codex may access; optionally wrap Codex runs in sandboxed worktrees.
3. Sanitize user-supplied prompts to avoid shell injection when constructing CLI commands.
4. Mask secrets in logs (Codex stdout/stderr) before persisting to Chroma.

### Phase 9 – Testing Strategy
1. Unit tests: profile loader, configuration parsing, Chroma event recording (use in-memory sqlite-backed Chroma or monkeypatched client).
2. Integration tests: run FastMCP server with a fake Codex runner to validate tool/resource contracts; leverage FastMCP testing harness.
3. Contract tests: confirm JSON Schema of tool arguments matches MCP expectations; include fixtures for host compatibility.
4. Smoke tests: spawn a sample general agent and ensure timeline + checklist stored as expected.
5. Add CI workflow (GitHub Actions) running `ruff`, `pytest`, and type checks (`mypy` or `pyright`).

### Phase 10 – Developer Experience & Tooling
1. Provide `hydra` CLI (Typer/Rich) to manage profiles, run mock sessions, flush Chroma, and inspect event logs.
2. Add developer docs on using context7/Jina (or alternative) during research/capture steps if those integrations become part of workflows.
3. Supply example MCP client notebooks/scripts demonstrating Codex delegation (e.g., call `spawn_agent` then `summarize_session`).
4. Offer VS Code tasks or Make targets for `dev`, `lint`, `test`, `run-mcp`.

### Phase 11 – Deployment & Operations
1. Containerize the server with multi-stage Dockerfile (install system deps, copy repo, set entrypoint to `python -m hydra_mcp.server`).
2. Provide Helm chart or ECS task definition for production deployment, including persistent volume for Chroma path.
3. Configure health probes/metrics (Prometheus or OpenTelemetry) and log shipping.
4. Prepare backup/export strategy for Chroma collection (periodic JSON dumps, S3 snapshots).

### Phase 12 – Documentation & Onboarding
1. Write `README.md` covering architecture, setup, running the MCP, and invoking Codex agents.
2. Document profile format with examples (generalist, code-reviewer, data-migration) and how to extend them safely.
3. Add runbooks for common tasks: rotating Codex credentials, clearing stuck sessions, restoring from Chroma backup.
4. Maintain changelog aligned with MCP spec versions.

### Phase 13 – Future Enhancements (Optional Roadmap)
1. Integrate semantic query UI or Slack bot using Chroma retrievals.
2. Support agent analytics dashboards (session durations, success rates) via lightweight API.
3. Explore embedding `context7`/`jina` search as additional MCP tools for richer research automation.
4. Add sampling support so Hydra can request LLM-generated follow-ups through the MCP sampling capability.

## 5. Risk & Mitigation Overview
- **Codex CLI availability**: add pre-flight checks and graceful fallbacks/mocks.
- **Chroma persistence volume**: monitor disk usage, offer pruning policies, and export warnings when near capacity.
- **Concurrent workspace mutations**: isolate agent sessions via ephemeral branches or worktrees; serialize operations touching identical paths.
- **Security & approval flows**: surface actions to users with descriptions (per MCP spec) and enforce manual approval before writing to git.

## 6. Milestone Breakdown (Indicative)
1. Week 1: Phases 0–2 (scaffolding, profiles, baseline MCP server).
2. Week 2: Phases 3–4 (Codex orchestration, Chroma persistence) with initial tests.
3. Week 3: Phases 5–7 (tool surface, multi-agent coordination, logging) plus integration tests.
4. Week 4: Phases 8–12 (security hardening, CI/CD, docs, deployment artifacts).
5. Ongoing: Phase 13 roadmap experimentation and user feedback loops.



## 14. Supporting Artifacts
- `docs/tool_catalog.md` – canonical tool descriptions with prompts and common use cases.
- `docs/multiagent_workflow.md` – multi-agent development blueprint covering Conport manager, coder, and reviewer loops.

