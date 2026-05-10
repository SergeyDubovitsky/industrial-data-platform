# Task Flow

Use this workflow for work that needs handoff between planning, architecture,
implementation, review, verification, docs, and release.

## 1. Plan

Role: `planner`

Output:

- Goal and scope.
- Out of scope.
- Write scopes.
- Validation commands.
- ADR and LikeC4 check.

## 2. Architecture

Role: `architect`

Output:

- Decision.
- Impacted artifacts.
- Constraints and risks.
- `ADR needed` or `ADR not needed`.
- `LikeC4 update needed` or `LikeC4 update not needed`.

## 3. Issue Readiness

Role: `status` or issue owner

Output:

- Acceptance criteria.
- Verification section.
- Links to relevant ADRs, contracts, C4 views, and write scopes.
- Subtasks when the work is too broad for one commit.

## 4. Implementation

Role: `worker`

Output:

- Minimal scoped diff.
- Implementation note.
- Tests added or updated.
- Open questions.

## 5. Review

Role: `reviewer`

Output:

- Decision: `ready` or `needs changes`.
- Findings ordered by severity.
- Test gaps.
- Follow-ups.

## 6. Verification

Role: `verifier`

Output:

- Commands run.
- Passed checks.
- Failed checks.
- Not-run checks and why.

## 7. Documentation

Role: `docs`

Output:

- Docs updated.
- Docs intentionally unchanged.
- User-visible notes.

## 8. Release

Role: `release`

Output:

- Commit, push, PR, or deploy summary.
- What was intentionally not delivered.

## 9. Status

Role: `status`

Output:

- Suggested issue state.
- Status comment.
- Validation summary.
- Residual risks.
