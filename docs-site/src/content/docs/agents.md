---
title: Agent Workflow
description: How agents should navigate the repository without loading unnecessary context.
---

The default agent path is deliberately short:

1. Root `AGENTS.md`
2. Closest scoped `AGENTS.md` for touched paths
3. `docs/agents/module-map.yaml`
4. The relevant living source-of-truth document
5. Archived ADR only if rationale is needed

## Ownership

Use `docs/agents/module-map.yaml` to map paths to modules, source-of-truth files,
and validation commands. Keep changes scoped to the requested module and its
ownership boundary.

## Decision context

Use `docs/architecture/decisions.md` as the active decision index. The ADR files
under `docs/architecture/adrs/archive/` are historical context and should not be
read as current requirements when a living doc or contract says otherwise.

## Docs-only validation

```bash
git diff --check
uv run --group integration python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('docs/agents/module-map.yaml').read_text())"
npm --prefix docs-site run build
```
