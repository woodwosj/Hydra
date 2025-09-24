# RESUMEWORK.md – Multi-Agent Orchestration Layer

## PROJECT STATUS SNAPSHOT
### Last Updated: 2025-09-24T02:37:38Z
### Session ID: hydra-session-20250924T023738Z
### Active Branch: main
### Workflow Stage: IMPLEMENTING

## EXECUTIVE SUMMARY
Hydra MCP remains in the implementation phase, now shipping diagnostics, replay hydration, and richer status reporting for the orchestration layer. Task/session/worktree state is persisted and auto-hydrated, while CLI tooling enables quick inspection of Chroma data. The critical path is finishing automatic task resume hooks and rounding out monitoring; no new blockers beyond the planned resume logic.

---

## COMPLETED WORK (Last 10 Items)
### Recently Completed ✅
- [x] **HYD-016:** Track session/worktree state in tool handles
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: cc298d6
  - Tests: `PYTHONPATH=src .venv/bin/pytest`
  - Notes: Tool handles now retain replayed state for status previews.

- [x] **HYD-015:** Regression test for diagnostics CLI
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: d57f0f2
  - Notes: Ensures CLI exits cleanly when Chroma unavailable.

- [x] **HYD-014:** Document diagnostics usage
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: c1c5882
  - Notes: README now covers `hydra_diag.py` commands.

- [x] **HYD-013:** Handle status errors when Chroma unavailable
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 6330415
  - Notes: Status resource safely reports storage errors.

- [x] **HYD-012:** Add Hydra diagnostics CLI
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: b266b3c
  - Notes: Introduced `scripts/hydra_diag.py` for task/worktree/session inspection.

- [x] **HYD-011:** Hydrate tasks on server startup
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 0045ce3
  - Notes: In-memory orchestration now repopulates from Chroma events.

- [x] **HYD-010:** Track session/worktree state in tool handles *(supersedes HYD-008)*
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: cc298d6
  - Notes: Provides live previews and hydration metadata.

- [x] **HYD-009:** Wire tracking into task lifecycle
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 5dab035
  - Notes: Task events emit Chroma records on state changes.

- [x] **HYD-008:** Expose tracking summaries in status endpoint
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 13d78ee
  - Notes: Status displays short previews of activity.

- [x] **HYD-007:** Add worktree and session tracking persistence
  - Completed: 2025-09-23
  - Agent: Coder Implementation
  - Commit: 94ffba6
  - Notes: Chroma store manages structured records.

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
- **HYD-017:** Auto-resume running tasks on startup
  - Status: PLANNING → IMPLEMENTING
  - Assigned: Conport Manager (context prep)
  - Context Package: CPK-2025-017
  - Blocking: None (depends on HYD-009 completion)
  - Review Iteration: N/A

### Parallel Tracks
- Worktree 1: feature/auto-resume – HYD-017 (prep)
- Worktree 2: feature/status-monitoring – HYD-018 (queued)
- Merge Scheduled: 2025-09-26

---

## COMPREHENSIVE TODO CHECKLIST

### 🔴 CRITICAL PATH (Blocks other work)
- [ ] HYD-017: Auto-resume running tasks on startup
  - Priority: P0
  - Estimated: 4 hours
  - Dependencies: HYD-009 (completed)
  - Context Needed: Replay hooks + session restart strategy

### 🟡 HIGH PRIORITY (Core features)
- [ ] HYD-018: Expand status & diagnostics endpoints
  - Priority: P1
  - Dependencies: HYD-017
  - Acceptance Criteria: Status/CLI expose replay metrics and health check

### 🟢 STANDARD PRIORITY
- [ ] HYD-019: Extend CLI for task filtering/resume triggers
- [ ] HYD-020: Document multi-agent workflow in README/docs

### 🔵 BACKLOG (Nice to have)
- [ ] HYD-021: Visualize task graph via web dashboard
- [ ] HYD-022: Slack notifications for agent handoffs

### DEPENDENCY GRAPH
```
HYD-017 → HYD-018 → HYD-019
HYD-017 → HYD-020

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
