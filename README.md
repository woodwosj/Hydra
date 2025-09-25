# Hydra MCP

Hydra MCP is a FastMCP-based Model Context Protocol server that orchestrates OpenAI
Codex agents, persists their activity in ChromaDB, and exposes tooling for multi-agent
software workflows. It is designed for operators who want Codex-driven automation with a
reviewable audit trail and lightweight monitoring hooks.

## Features
- **Codex orchestration:** Spawn, resume, and track Codex CLI sessions through MCP tools.
- **Persistent context:** Record tasks, session notes, worktrees, and resume attempts in
  ChromaDB for replay and semantic search.
- **Task lifecycle tools:** Create, start, inspect, and complete multi-agent tasks with
  configurable profiles and checklists.
- **Diagnostics & monitoring:** Use `hydra_diag.py` for metrics/status dumps and
  `hydra_alert_forwarder.py` to forward resume alerts into external monitoring systems.
- **Comprehensive tests:** Pytest suite covering Codex adapters, storage, tools, and CLI
  utilities for confident iteration.

## Repository Tour
- `src/hydra_mcp/` – Hydra MCP server, configuration, profile loader, and tool registry.
- `scripts/` – Operational utilities (`hydra_diag.py`, `hydra_alert_forwarder.py`).
- `profiles/` – Example agent profile definitions (generalist, code reviewer).
- `docs/` – Roadmap, workflow guide, tool catalog, and monitoring playbooks.
- `tests/` – Pytest coverage for storage, tools, CLI surfaces, and resume automation.

## Quickstart
1. Ensure Python 3.10+ is available and create a virtual environment.
2. Install Hydra MCP with optional development extras:
   ```bash
   pip install -e .[dev]
   ```
3. Copy `.env.example` to `.env` and set:
   - `CODEX_PATH` – Absolute path to the Codex CLI binary (optional if Codex is in PATH).
   - `CODEX_DEFAULT_MODEL` – Default model flag to pass to Codex (optional).
   - `CHROMA_PERSIST_PATH` – Location for the embedded Chroma store (default `./storage/chroma`).
4. Launch the server:
   ```bash
   python -m hydra_mcp.server
   ```
5. From an MCP host, list Hydra tools or fetch the status resource:
   - Tools: `list_agents`, `spawn_agent`, `query_context`, `summarize_session`, task lifecycle tools, and more.
   - Status: `resource://hydra/status` returns runtime metadata, Codex availability, and resume metrics.

## Diagnostics & Monitoring
- Inspect persisted state:
  ```bash
  PYTHONPATH=src python scripts/hydra_diag.py metrics
  PYTHONPATH=src python scripts/hydra_diag.py alerts --limit 5
  ```
- Forward resume alerts to logs or webhooks (see `docs/resume_alert_monitoring.md`):
  ```bash
  PYTHONPATH=src python scripts/hydra_alert_forwarder.py --format text --limit 10
  ```

## Development Workflow
- Run the full test suite:
  ```bash
  PYTHONPATH=src pytest
  ```
- Linting (if Ruff is installed via `.[dev]` extras):
  ```bash
  ruff check src tests
  ```
- Regenerate documentation or update profiles as features evolve. `RESUMEWORK.md` tracks
  high-level roadmap checkpoints and recent worklog entries.

## Documentation
- Implementation plan: `docs/hydra_mcp_plan.md`
- Tool catalog: `docs/tool_catalog.md`
- Multi-agent workflow blueprint: `docs/multiagent_workflow.md`
- Resume alert monitoring playbook: `docs/resume_alert_monitoring.md`

## License
Hydra MCP is released under the MIT License. See `LICENSE` for details.
