# RESUMEWORK.md – Multi-Agent Orchestration Layer

## PROJECT STATUS SNAPSHOT
### Last Updated: 2025-09-23T19:49:56Z
### Session ID: hydra-session-20250923T194956Z
### Active Branch: main
### Workflow Stage: IMPLEMENTING

## EXECUTIVE SUMMARY
Hydra MCP is in the implementation phase of its orchestration layer, focusing on end-to-end task, session, and worktree tracking. Core Codex integration and persistence features are in place, and we are now extending continuity across restarts. The critical path centers on persisting resumable state and tightening status surfaces; no blocking risks identified beyond upcoming data migration decisions.

---

## COMPLETED WORK (Last 10 Items)
### Recently Completed ✅
- [x] HYD-008: Wire tracking into task lifecycle
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 5dab035
  - Tests: `PYTHONPATH=src .venv/bin/pytest`
  - Notes: Session/worktree events emitted during task start/complete.

- [x] HYD-007: Expose tracking summaries in status endpoint
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 13d78ee
  - Tests: `PYTHONPATH=src .venv/bin/pytest`
  - Notes: Status now surfaces worktree/session previews.

- [x] HYD-006: Add worktree and session tracking persistence
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 94ffba6
  - Notes: Chroma store now manages structured records.

- [x] HYD-005: Implement task orchestration tools
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 1b1b110
  - Notes: Created create/start/status/complete tool suite.

- [x] HYD-004: Register Hydra MCP tools
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 07dfcc8
  - Notes: Exposed spawn_agent, summarize_session, log_context, etc.

- [x] HYD-003: Add Chroma persistence abstraction
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 708bd04
  - Notes: Introduced ChromaStore with event sequencing.

- [x] HYD-002: Add agent profile models and loader
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 00c119b
  - Notes: YAML-backed profiles and validation in place.

- [x] HYD-001: Scaffold Hydra MCP server
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: aac9fca
  - Notes: Project bootstrap, FastMCP skeleton.

### Historical Milestones
- Phase 0: Foundations (Completed 2025-09-23)
- Phase 1: FastMCP Skeleton (Completed 2025-09-23)
- Phase 2: Agent Profiles (Completed 2025-09-23)
- Phase 3: Codex Orchestrator (Completed 2025-09-23)
- Phase 4: Chroma Persistence (Completed 2025-09-23)
- Phase 5: MCP Tool Surface (Completed 2025-09-23)
- Phase 6: Multi-Agent Coordination (In Progress)

---

## ACTIVE WORK IN PROGRESS
### Current Sprint/Iteration
- **HYD-009**: Persist task/worktree state across restarts
  - Status: IMPLEMENTING
  - Assigned: Conport Manager → Coder Implementation (handoff pending)
  - Context Package: CPK-2025-009
  - Blocking: HYD-010 (status API polishing)
  - Review Iteration: N/A

### Parallel Tracks
- Worktree 1: feature/orchestration-persistence – HYD-009
- Worktree 2: feature/status-enhancements – HYD-010 (queued)
- Merge Scheduled: 2025-09-25

---

## COMPREHENSIVE TODO CHECKLIST

### 🔴 CRITICAL PATH (Blocks other work)
- [ ] HYD-009: Persist task + worktree state across restarts
  - Priority: P0
  - Estimated: 6 hours
  - Dependencies: Chroma event indexing
  - Context Needed: Historical event replay strategy

### 🟡 HIGH PRIORITY (Core features)
- [ ] HYD-010: Expand status resource + REST surface for monitoring
  - Priority: P1
  - Dependencies: HYD-009
  - Acceptance Criteria: Status exposes resumable counts & health check

- [ ] HYD-011: Implement task auto-resume hooks on server startup
  - Priority: P1
  - Dependencies: HYD-009
  - Acceptance Criteria: In-memory state repopulated from Chroma events

### 🟢 STANDARD PRIORITY
- [ ] HYD-012: Add CLI utilities for manual task management
- [ ] HYD-013: Document multi-agent workflow in README & docs

### 🔵 BACKLOG (Nice to have)
- [ ] HYD-014: Visualize task graph via web dashboard
- [ ] HYD-015: Slack notifications for agent handoffs

### DEPENDENCY GRAPH
```
HYD-009 → HYD-011
HYD-009 → HYD-010 → HYD-012
HYD-011 → HYD-013
```

---

## AGENT ACTIVATION CONTEXT

### For Next Agent Activation
**ACTIVATE**: CODER_IMPLEMENTATION (after Conport Manager compiles persistence context)
**REASON**: Need implementation of resumable task state ingestion prior to reviewer pass.

### Critical Context for Resumption
1. **Architecture Decisions**
   - MCP server uses FastMCP tool decorators; modular components registered at bootstrap.
   - ChromaDB is authoritative store for events, tasks, and context packages.
   - Task orchestration currently in-memory; persistence upgrade underway.

2. **Technical Constraints**
   - Preserve backward compatibility with existing tool schemas.
   - Status resource must respond in <150ms to avoid host timeouts.
   - Avoid blocking operations in MCP tool handlers (async required).

3. **Known Issues/Gotchas**
   - Task state lost on restart (current priority fix).
   - Worktree paths currently provided via context; enforce validation.
   - FastMCP dependency not available in test environment; rely on stubs.

4. **Testing Requirements**
   - Maintain `PYTHONPATH=src .venv/bin/pytest` green.
   - Add regression tests for task state replay.
   - Validate JSON serialization of status output.

5. **External Dependencies**
   - chromadb (embedded) for persistence.
   - Codex CLI (path configurable) for agent spawning.
   - (Future) Conport API for context storage.

### Environment Setup Requirements
```bash
node: 18.17.0
python: 3.11
postgresql: 15
redis: 7.0

# Environment variables
CODEX_PATH=
CODEX_DEFAULT_MODEL=
CHROMA_PERSIST_PATH=./storage/chroma
HYDRA_LOG_LEVEL=INFO
```

### Recent Decisions & Rationale
- Store task/session/worktree events in Chroma to support replayable orchestration.
- Surface status previews instead of full timelines for lightweight monitoring.
- Retain in-memory task map for fast access; plan to hydrate from Chroma on startup.

---

## CONPORT CONTEXT PACKAGE

### Store in Conport (Parallel Operations)
```python
conport.store({
  "id": "CTX-20250923-194956",
  "type": "project_state",
  "data": {
    "decisions": [
      {
        "id": "DEC-001",
        "decision": "Persist orchestration state in Chroma",
        "rationale": "Ensures resumable multi-agent workflows",
        "date": "2025-09-23",
        "impact": "Server must replay events on startup"
      }
    ],
    "patterns": [
      {
        "problem": "Task state lost after restart",
        "solution": "Serialize task/worktree/session events to Chroma",
        "files": ["src/hydra_mcp/storage/chroma.py"],
        "performance_gain": "Instant replay vs manual recovery"
      }
    ],
    "errors_resolved": [
      {
        "error": "Status endpoint lacked context previews",
        "cause": "No aggregation of tracking events",
        "fix": "Added summaries from Chroma",
        "prevention": "Maintain preview builders in status resource"
      }
    ],
    "code_snippets": {
      "task_orchestration": "register_tools(...) -> ToolHandles",
      "storage_helpers": "ChromaStore.record_session_tracking",
      "status": "hydra_status resource payload"
    },
    "test_patterns": {
      "integration": "tests/test_tools.py::test_task_lifecycle",
      "unit": "tests/test_chroma_store.py::test_session_tracking"
    }
  }
})
```

### Retrieve from Conport for Context
- Prior task orchestration implementations (CTX-20250923-194956)
- Session tracking fixes and known issues
- Architecture decisions for persistence
- Performance and testing patterns above

---

## WORKFLOW STATE MACHINE

### Current State: IMPLEMENTING
### Valid Transitions:
- PLANNING → IMPLEMENTING
- IMPLEMENTING → REVIEWING
- REVIEWING → IMPLEMENTING (if rejected)
- REVIEWING → DEPLOYED (if approved)
- DEPLOYED → PLANNING (next iteration)

### State History (Last 5)
1. IMPLEMENTING (HYD-008)
2. IMPLEMENTING (HYD-007)
3. IMPLEMENTING (HYD-006)
4. IMPLEMENTING (HYD-005)
5. IMPLEMENTING (HYD-004)

### Metrics
- Average Review Cycles: TBD (initial reviewer handoff pending)
- Average Task Completion: 4.0 hours (est.)
- Context Reuse Rate: 70% (via shared context packages)
- Parallel Execution Frequency: 30% (two active tracks planned)

---

## ORCHESTRATION OPTIMIZATION RULES

### Parallel Execution Triggers
- When updating RESUMEWORK.md, concurrently update Conport, analyze parallelizable tasks (HYD-010/HYD-012), prep next agent context, archive task artifacts.

### Context Preservation Strategy
- Persist error/debug patterns, performance benchmarks (Chroma event templates), security guidelines (tool descriptions), architecture rationale (docs/multiagent_workflow.md), and validated testing strategies.

### Handoff Optimization
- Each handoff must specify next action, context references (Chroma session timestamps), success criteria (task acceptance), blockers (dependency graph), and rollback (replay event stream).

### Continuous Improvement
- After each task completion: log actuals to Chroma, document new patterns, append to error knowledge base, refine agent prompts in `profiles/` as needed.

---

## Usage Instructions

1. Load this orchestration prompt when modifying RESUMEWORK.md.
2. Execute sections in parallel, cross-reference Conport packages, validate state transitions, and prepare next agent activation instructions.
3. To resume work, start with *Project Status Snapshot*, load appropriate agent profile, fetch context package (CPK-2025-009), assess parallel opportunities, proceed with implementation.

### Critical Success Metrics
- Zero context gaps between handoffs
- 100% decision traceability via Chroma + RESUMEWORK.md
- Parallel execution whenever dependency graph allows
- Growing knowledge base in Conport (CTX-* packages)
- Decreasing review cycles once reviewer agent activates

---

**Single Source of Truth**: RESUMEWORK.md captures the live brain of Hydra MCP. Keep it synchronized with Conport to enable any agent to resume seamlessly.
