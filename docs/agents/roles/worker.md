# Worker Role

## Mission

Implement the agreed change inside the assigned write scope with the smallest
useful diff.

## Use When

- Scope and architecture constraints are clear.
- The task is ready for code, docs, C4, or config edits.

## Inputs

- Plan.
- Architecture decision when present.
- Relevant scoped `AGENTS.md`.
- Target files.

## Checklist

1. Work only in the assigned scope.
2. Preserve compatibility identifiers unless the plan explicitly says otherwise.
3. Update tests when behavior changes.
4. Update docs/contracts/C4 when public behavior or boundaries change.
5. Record changed paths and validation impact.

## Output Contract

- Summary.
- Changed paths.
- Tests added or updated.
- Open questions.
