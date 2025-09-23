# Hydra Multi-Agent Workflow Blueprint

This document codifies the development loop for Hydra's three-agent crew consisting of
**Conport Manager**, **Coder**, and **Code Reviewer**. The workflow emphasizes parallelism,
rich context handoffs, and explicit approval gates.

## 1. Planning & TODO Expansion (Conport Manager)
1. Inspect current repository state, recent commits, and open issues.
2. Query Hydra's Chroma-backed context store for relevant history (`query_context`).
3. Use context7 and web search to gather up-to-date references, standards, and API docs.
4. Consolidate findings via `log_context` into a “context package” tagged for the next agent.
5. Build or update the project-wide TODO checklist in Chroma, capturing:
   - Task description and priority.
   - Target agent type.
   - Entry criteria and required assets.
   - Exit criteria and validation signals.
6. When multiple independent subtasks are uncovered, schedule them concurrently and
   spawn dedicated agents for each using the `task` tool (see §4) to maximize throughput.

## 2. Subtask Activation Cycle
For each item in the TODO checklist, the following loop applies:

### 2.1 Context Preparation (Conport Manager)
- Revisit the context package, augmenting with:
  - Latest repository diffs and relevant files.
  - External research obtained via context7/web queries.
  - Applicable code snippets or architectural diagrams.
- Ensure separate git worktrees are created for tasks touching distinct areas. Record the
  worktree path inside the context payload.
- Invoke `spawn_agent` with profile `generalist` or `coder` to initiate the implementation
  phase, passing:
  - `task_brief` summarizing deliverables and constraints.
  - `inputs.context_package` containing research, file paths, and worktree details.
  - `flags` such as `--model` or `--ask-for-approval` as required.

### 2.2 Implementation (Coder Agent)
- Consume the context package from Conport.
- Produce a detailed execution plan, aligning actions with the checklist.
- Execute updates inside the assigned worktree, adding tests and validation commands.
- Log intermediate artifacts with `log_context` (screenshots, diffs, benchmark results).
- Upon completion, transition the worktree to a staging state (no commit yet) and trigger
  the reviewer via the task tool.

### 2.3 Review & Approval (Code Reviewer Agent)
- Review updated files, tests, and context package.
- Run `summarize_session` on the coder's session to ensure no hidden blockers remain.
- Evaluate against the reviewer checklist (correctness, coverage, security, style).
- Outcome branches:
  - **Approve**: reviewer is responsible for committing within the worktree and pushing
    to the shared branch. Update Chroma with approval notes.
  - **Reject**: record a review document (issues, rationale, required fixes) and call
    Conport manager for remediation.

## 3. Rejection Loop & Remediation
When the reviewer rejects a session:
1. Reviewer calls `log_context` with detailed feedback, error logs, and test expectations.
2. Reviewer requests Conport manager assistance, passing the rejection payload.
3. Conport manager performs targeted research:
   - Use context7/web search to gather troubleshooting guidance.
   - Query historical sessions to spot similar incidents.
   - Update the context package with new references, sample fixes, and debugging steps.
4. Spawn a new coder session referencing the enriched context package.
5. Repeat the coder → reviewer cycle until approval is secured.

## 4. Task Tool Usage
Hydra’s MCP integration should expose a high-level **task** tool used by hosts to manage
parallel delegation:
- **create_task** – open a task, assign agent type, and attach context bundle.
- **start_task** – launch the corresponding agent via `spawn_agent`.
- **status_task** – monitor active sessions across worktrees.
- **complete_task** – mark task finished after reviewer approval and merge.

Conport manager is responsible for invoking these task operations, ensuring different
worktrees remain isolated until convergence. When multiple tasks complete, Conport
manager coordinates merges (rebase, conflict resolution) before pushing to the main
branch.

## 5. Context Packaging Guidelines
- Store context packages in Chroma under structured IDs (`task/{id}/context`).
- Include: task brief, file list, git worktree path, research links, checklist expectations,
  known risks, validation requirements.
- Maintain version history so agents can diff successive context updates.

## 6. Approval & Deployment Flow
1. Reviewer commits approved changes inside the worktree.
2. Conport manager collects reviewer notes and publishes summary via `summarize_session`.
3. If multiple worktrees were active, Conport manager merges sequentially, ensuring
   conflict-free integration, running full validation after each merge.
4. When ready, Conport manager pushes to staging or production branches per project policy.

## 7. Parallelization Best Practices
- Always initialize new tasks via the task tool to make concurrency explicit.
- Launch agents simultaneously for independent tasks to maximize throughput.
- Keep reviewer capacity in mind: stagger approvals to avoid bottlenecks.
- Use `query_context` for rapid retrieval of prior art to minimize redundant research.

---

This blueprint should be kept up to date as Hydra’s toolset evolves. Embed references to
this workflow in MCP prompt definitions to guide agents automatically.
