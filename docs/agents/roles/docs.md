# Docs Role

## Mission

Keep durable documentation aligned with changed behavior and architecture.

## Use When

- User-visible behavior, contracts, setup, architecture, or workflows change.
- Documentation structure or navigation changes.

## Inputs

- Diff.
- Plan.
- Verification note.
- Relevant README, contracts, ADRs, and C4 files.

## Checklist

1. Identify stale docs.
2. Update only docs touched by the behavior or boundary change.
3. Preserve source-of-truth order from root `AGENTS.md`.
4. Record docs intentionally left unchanged.

## Output Contract

- Docs updated.
- Docs intentionally unchanged.
- User-visible notes.
