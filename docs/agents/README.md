# Agent Workspace Guide

This directory contains tracked handoff material for AI agents. It complements
the root `AGENTS.md` and should stay short enough to be useful in a fresh clone.

## Start Here

1. Read the root `AGENTS.md`.
2. Read the nearest scoped `AGENTS.md` for the files you will touch.
3. Open `module-map.yaml` to identify the owner, source of truth, and validation
   commands.
4. For large tasks, use `workflows/task-flow.md` and the role prompts
   in `roles/`.

## How To Run Agents

- Codex: start from the repository root when possible, state the module owner,
  write scope, forbidden identifiers, and validation command in the prompt. For
  scoped work, tell Codex to read the nearest scoped `AGENTS.md`.
- Claude Code: `CLAUDE.md` imports the root `AGENTS.md`; still name the scoped
  `AGENTS.md` and module-map entry that apply to the task.
- GitHub Copilot: use `.github/copilot-instructions.md` plus `AGENTS.md`; check
  Copilot response references when repository instructions should apply.
- Parallel agents: split write scopes clearly, for example contracts/docs,
  code/tests, and read-only review. Do not give two agents the same write scope.
- Skills: use repo-scoped skills for repeated high-risk workflows; do not use
  them as a replacement for `AGENTS.md`.

## What Belongs Here

- Stable workflow and handoff instructions.
- Role prompts that can be reused by any agent.
- Templates for task planning, implementation notes, reviews, verification, and
  status updates.
- A machine-readable module map.

## What Does Not Belong Here

- Local task scratchpads.
- Customer secrets or credentials.
- Generated outputs from one agent run.
- Raw issue tracker exports.

Use `.local/agent-runs/` for local scratch work. `.local/` is intentionally
ignored by git.

## References

This structure follows common agent-context practices:

- root repository instructions for Codex-style agents
- short compatibility bridge files for tools with their own instruction names
- scoped instructions close to owned code
- a machine-readable module map for ownership and validation
- workflow and handoff templates for long-running tasks

## Documentation Shape

Follow the Diataxis split when writing durable documentation:

- Tutorials teach a workflow.
- How-to guides solve a specific task.
- Reference documents define exact behavior and fields.
- Explanation documents capture concepts, trade-offs, and rationale.
