# Architecture Docs Guide

Scope: `docs/architecture/`.

This directory captures current state, the compact decision register, glossary,
open questions, explanatory architecture notes, and archived ADR rationale.

## Do

- Keep `decisions.md` compact and focused on active decisions.
- Keep archived ADRs historical; do not treat them as current source-of-truth.
- Update `current-state.md` when the working snapshot changes.
- Update `glossary.md` when terminology changes.
- Update `open-questions.md` when a decision is made or a new blocker appears.
- Keep LikeC4 in `arch/likec4/` as the diagram source of truth.

## Do Not

- Do not duplicate full contract field definitions here.
- Do not silently contradict `decisions.md`; update the living source-of-truth
  doc and add rationale only when a new significant trade-off needs it.
- Do not use `Monitoring & Alarm Platform` as the current central system name.

## Validation

- Docs-only: `git diff --check`
- If architecture model changes too: `cd arch && npm run validate`
