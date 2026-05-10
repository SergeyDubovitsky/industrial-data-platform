---
title: Start Here
description: Internal entrypoint for humans and AI agents working in the Industrial Data Platform repository.
---

This site is a curated internal index over the repository documentation. It does
not replace the canonical markdown files in `docs/`, `apps/*/docs/`, or
`arch/likec4/`; it makes the first read path smaller and easier to scan.

## Reading order

1. Read `AGENTS.md` at the repository root.
2. Read `docs/agents/module-map.yaml` for ownership and validation.
3. Read `docs/architecture/current-state.md` and
   `docs/architecture/glossary.md` for orientation.
4. Read `docs/contracts/README.md` before changing MQTT, Kafka, ClickHouse,
   storage, or schema boundaries.
5. Use `docs/architecture/decisions.md` for active decisions.
6. Open `docs/architecture/adrs/archive/` only when you need historical
   rationale or rejected alternatives.

## Source-of-truth order

- `docs/contracts/`: wire contracts, topic names, table names, schema details.
- `arch/likec4/`: C4 systems, containers, ownership, dependencies, deployment views.
- `docs/architecture/current-state.md`: current working system snapshot.
- `docs/architecture/decisions.md`: active decision register.
- Package READMEs and implementation guides: local usage notes.

## Validation anchors

Use `docs/agents/module-map.yaml` to select validation commands for the files
you touch. For docs-only changes, the baseline is:

```bash
git diff --check
uv run --group integration python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('docs/agents/module-map.yaml').read_text())"
npm --prefix docs-site run build
```
