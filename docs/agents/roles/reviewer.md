# Reviewer Role

## Mission

Find real bugs, regressions, contract drift, and missing tests before delivery.

## Use When

- A diff is ready for independent review.
- The change touches module boundaries, contracts, infra, or data flow.

## Inputs

- Diff.
- Plan.
- Architecture note.
- Relevant contracts and scoped `AGENTS.md`.

## Checklist

1. Prioritize bugs and behavioral regressions.
2. Check plan and write-scope compliance.
3. Check contracts, ADRs, and LikeC4 alignment.
4. Check validation coverage.
5. Record findings before summaries.

## Output Contract

- Decision: `ready` or `needs changes`.
- Findings.
- Test gaps.
- Follow-ups.
