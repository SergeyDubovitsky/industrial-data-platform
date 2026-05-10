---
name: github-issue-workflow
description: Use when implementing or preparing work from a GitHub issue in this repository: read and review the issue, define ready/done gates, ask clarifying questions, update the agreed scope, create a safe issue branch from the latest mainline, check current external library docs with context7 when needed, implement with TDD, run validation, fix failures, document the result, and prepare issue or PR status.
---

# GitHub Issue Workflow

Use this skill when a user asks to work from a GitHub issue, issue URL, issue
number, or issue-driven task.

## Read First

1. `AGENTS.md`
2. `docs/agents/module-map.yaml`
3. The closest scoped `AGENTS.md` for affected paths
4. `docs/agents/workflows/task-flow.md`
5. Relevant architecture model files under `arch/likec4/`, selected by the
   affected module in `docs/agents/module-map.yaml`
6. Relevant role prompts:
   - `docs/agents/roles/architect.md`
   - `docs/agents/roles/docs.md`
   - `docs/agents/roles/reviewer.md`
   - `docs/agents/roles/verifier.md`

## Workflow

1. Read the GitHub issue.
   - Prefer the GitHub app or `gh issue view`.
   - Capture title, body, labels, linked PRs, comments, acceptance criteria,
     affected modules, and any attached logs or screenshots.
   - Check logs, screenshots, and pasted config for secrets or sensitive data;
     do not copy secrets into commits, docs, PRs, or issue comments.
   - If the issue cannot be read, ask the user for the issue URL or content.

2. Review readiness before coding.
   - Use the architect role to check boundaries, contracts, C4, deployment,
     ADR impact, module ownership, and compatibility identifiers.
   - Use existing LikeC4 model context as architecture input, especially
     systems, containers, relationships, deployment views, and ownership
     boundaries for the affected module.
   - Use the docs role to check whether README, contracts, C4, ADRs, guides,
     or user-facing notes will need updates.
   - Use the reviewer role to identify likely regressions, missing acceptance
     criteria, missing tests, and risky assumptions.
   - If the issue conflicts with `docs/contracts/`, `arch/likec4/`, or
     `docs/architecture/`, flag the conflict and do not silently choose the
     issue over the repository source of truth.
   - If the issue implies a breaking contract, ClickHouse, Kafka, MQTT, Docker,
     package, entrypoint, or compatibility identifier change, stop and ask for
     an explicit migration plan or user approval.
   - Use delegated subagents only when the active environment allows it and the
     user explicitly asked for delegation or parallel agent work.

3. Define ready and done.
   - Definition of Ready: goal, scope, out of scope, acceptance criteria,
     affected modules, write scope, architecture/contract/docs impact, and
     required validation are clear.
   - Definition of Done: implementation is complete, each acceptance criterion
     maps to a test or validation result, required docs/LikeC4 updates are
     complete or intentionally skipped, and validation evidence is recorded.
   - Do not start implementation until blockers in Definition of Ready are
     resolved or explicitly accepted by the user.

4. Ask clarifying questions when the issue is not ready.
   - Ask only the questions that block a correct implementation.
   - Do not implement against ambiguous acceptance criteria, unclear ownership,
     or conflicting source-of-truth documents.
   - When answers change scope or acceptance criteria, propose that the user
     record the clarified requirements in the issue, issue comment, or local
     plan before implementation continues.

5. Prepare the branch safely.
   - Check `git status --short` first and do not overwrite unrelated work.
   - Do not run destructive commands or auto-stash user changes unless the
     user explicitly approves that action.
   - Determine the mainline branch from the repository context, usually
     `main`, `master`, or `origin/HEAD`.
   - Switch to the mainline branch and pull with a fast-forward-only update:
     `git switch <mainline>` then `git pull --ff-only`.
   - Before creating a new branch, check for existing local/remote branches or
     open PRs that already reference the issue number; reuse the right branch
     when it is clearly the current work branch.
   - Create an issue branch using one of:
     - `codex/feature/<issue-number>-<short-slug>`
     - `codex/bug/<issue-number>-<short-slug>`
     - `codex/bugfix/<issue-number>-<short-slug>`
   - Choose the prefix from the issue type, labels, or user instruction.
   - If the user or repository policy requires another branch prefix, keep the
     issue type, issue number, and slug in the branch name.

6. Implement with TDD.
   - Map each acceptance criterion to a failing test, existing test, manual
     validation command, or explicit "not automated" rationale.
   - When using, installing, upgrading, or debugging any external library,
     framework, or service API, use the `context7` skill first to fetch current
     documentation instead of relying on memory.
   - Record the library id/query or docs source checked when it affects an
     implementation choice.
   - Add or update the smallest useful failing test first.
   - Run the targeted failing test and confirm it fails for the expected reason.
   - Implement the minimal scoped change.
   - Rerun the targeted test until it passes.
   - For Python implementation work, use the `python-clean-architecture` skill.
   - For Python tests, prefer the repository pytest patterns and use the
     `python-testing` skill when test structure or fixtures are non-trivial.

7. Validate.
   - Run validation from `docs/agents/module-map.yaml` for affected modules.
   - Run lint checks when code changed.
   - Run integration tests when data paths, contracts, local infra, Kafka,
     MQTT, ClickHouse, or cross-module behavior changed.
   - If docs, contracts, or C4 changed, run their required validation too.

8. Fix validation results.
   - Investigate failures instead of weakening tests.
   - Fix the implementation, tests, docs, or contracts as needed.
   - Rerun the failed checks and any nearby checks that could be affected.

9. Self-review before delivery.
   - Check for scope creep, accidental compatibility changes, unnecessary
     abstractions, missing tests, docs drift, and LikeC4 drift.
   - Reconcile the implementation against Definition of Done before preparing
     final status.

10. Document the implementation when needed.
   - Update durable docs only when behavior, setup, contracts, public
     interfaces, architecture, or operational workflows changed.
   - Update `arch/likec4/` when implementation changes durable architecture:
     module boundaries, systems, containers, relationships, dependencies,
     deployment paths, runtime ownership, or data-flow shape.
   - Use the `likec4-dsl` skill for non-trivial LikeC4 edits.
   - Preserve the source-of-truth order from `AGENTS.md`.
   - Record docs intentionally unchanged when no durable update is required.

11. Commit, push, and create a PR after implementation.
   - After implementation, required docs/LikeC4 updates, self-review, and
     successful validation, commit the completed work.
   - Stage only files that belong to the issue; never include unrelated dirty
     worktree changes.
   - Use a concise commit message that references the issue number.
   - Push the issue branch and create a PR that links the issue.
   - The PR body must include implementation summary, acceptance criteria/test
     mapping, validation results, docs/LikeC4 note, and residual risks.
   - If validation is blocked or failing, do not present the PR as ready; create
     a draft PR only when the user wants a visible work-in-progress.
   - Prepare a concise issue comment when useful: what changed, validation
     results, docs/LikeC4 status, and anything intentionally out of scope.

## Output

- Issue summary and readiness decision.
- Clarifying questions asked, or "none needed".
- Definition of Ready and Definition of Done.
- Branch name and mainline branch used.
- Implementation summary and changed paths.
- Acceptance criteria mapped to tests, validation, or rationale.
- External library docs checked with `context7`, or "not applicable".
- Documentation and LikeC4 updated, or why they were not needed.
- Validation commands run, passed, failed, and not run.
- Residual risks and suggested issue/PR status.
