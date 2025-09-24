# Hydra MCP

Hydra MCP implements the Model Context Protocol (MCP) to let OpenAI Codex spawn scoped,
headless agent sessions that share a persistent memory layer backed by ChromaDB.

## Project Status
- Implementation is in early scaffolding.
- The long-form roadmap lives in `docs/hydra_mcp_plan.md` and tracks the planned phases.

## Development Quickstart
1. Create and activate a Python 3.10+ virtual environment.
2. Install the project in editable mode with development tooling:
   ```bash
   pip install -e .[dev]
   ```
3. Copy `.env.example` to `.env` and adjust paths/models as needed.
4. Run the MCP server locally:
   ```bash
   python -m hydra_mcp.server
   ```

The server currently exposes a single health resource at `resource://hydra/status` while
we build out Codex orchestration and Chroma persistence.

## Documentation
- Implementation roadmap: `docs/hydra_mcp_plan.md`
- Tool catalog: `docs/tool_catalog.md`
- Multi-agent workflow blueprint: `docs/multiagent_workflow.md`

## Diagnostics
- Run `PYTHONPATH=src .venv/bin/python scripts/hydra_diag.py tasks --json` to inspect persisted tasks (requires chromadb).
- `scripts/hydra_diag.py worktrees` and `sessions` surface worktree/session tracking data.
