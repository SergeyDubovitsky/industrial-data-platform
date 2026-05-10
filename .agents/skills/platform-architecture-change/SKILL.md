---
name: platform-architecture-change
description: Use when changing or reviewing Industrial Data Platform architecture, LikeC4/C4 models, ADRs, module boundaries, ownership, deployment views, or runtime module introduction. Do not use for narrow code edits without architecture impact.
---

# Platform Architecture Change

Use this skill before changing durable architecture boundaries or diagrams.

## Read First

1. `AGENTS.md`
2. `docs/agents/module-map.yaml`
3. The closest scoped `AGENTS.md` for affected paths
4. `docs/architecture/adrs/ADR-014-data-platform-core-and-modules.md`
5. Relevant files in `arch/likec4/` and `docs/architecture/`

## Boundary Rules

- Keep `Industrial Data Platform` as the core data collection, delivery,
  contracts, configuration, and storage boundary.
- Keep `Web Monitoring Module` and `Alarm Management Module` as modules above
  the data platform.
- Do not reintroduce `Monitoring & Alarm Platform` as the central system name.
- Do not add a new Alarm Management runtime package until alarm use cases are
  selected and the task explicitly includes that increment.
- Do not rename runtime identifiers, package names, Docker names, Kafka topics,
  ClickHouse tables, or contract ids without an approved migration plan.
- Use `docs/contracts/` for field-level contract details; C4 should show
  ownership, containers, dependencies, and deployment views.

## Workflow

1. Classify the impact: module ownership, data flow, deployment, contract,
   runtime package, or documentation-only boundary wording.
2. Decide whether ADR, LikeC4, current-state, glossary, or contract docs must
   change before implementation.
3. For LikeC4 edits, use the repo C4 patterns and validate with
   `cd arch && npm run validate`.
4. Keep code changes scoped to the owning module from `module-map.yaml`.
5. Record open questions instead of silently inventing module behavior.

## Output

- Architecture decision or "ADR not needed" rationale.
- Impacted modules and source-of-truth files.
- Required C4/docs/contracts updates.
- Validation run or intentionally not run.
