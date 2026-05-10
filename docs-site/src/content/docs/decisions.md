---
title: Decisions
description: Active decision register and archived rationale policy.
---

The active decision index lives at `docs/architecture/decisions.md`.

Use it to answer:

- What is the current accepted decision?
- Which living document owns the current details?
- Where is the archived rationale if a trade-off needs to be revisited?

## ADR archive policy

ADRs are kept under `docs/architecture/adrs/archive/` as historical rationale.
They explain why earlier decisions were made and which alternatives were
rejected. They are not the default source-of-truth for current behavior.

New significant decisions should update:

- the relevant living source-of-truth document;
- `docs/architecture/decisions.md`;
- archived rationale only when the trade-off is important enough to preserve.
