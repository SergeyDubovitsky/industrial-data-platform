# Agent Instructions

This file is the canonical entrypoint for AI agents working in this repository.
Read it first, then read the closest scoped `AGENTS.md` for the paths you touch,
and finally check `docs/agents/module-map.yaml` for ownership and validation.

## Mission

This repository is an industrial data collection platform monorepo. The current
architecture is:

- `Industrial Data Platform`: data ingestion, delivery, contracts, Kafka event
  log, Config Registry, ClickHouse Telemetry Store, PostgreSQL Platform Store,
  and local data-platform infrastructure.
- `Edge Telemetry Agent`: on-site runtime that reads southbound sources,
  normalizes observations, buffers locally, and publishes telemetry/status.
- `Web Monitoring Module`: dashboards, history, latest values, and read-only
  visualization over data-platform read models.
- `Alarm Management Module`: future rule engine, alarm lifecycle, workflow, and
  notifications. Runtime code is not present yet.

## Source Of Truth

Use this order when sources disagree:

1. `docs/contracts/` for MQTT/Kafka/ClickHouse/storage wire contracts, topic
   names, table names, schema details, and compatibility.
2. `arch/likec4/` for C4 systems, containers, ownership, dependencies, and
   deployment views.
3. `docs/architecture/current-state.md`, `docs/architecture/glossary.md`, and
   `docs/architecture/open-questions.md` for the current working snapshot.
4. `docs/architecture/decisions.md` for the compact decision register.
5. Package READMEs and implementation guides for local usage details.

Archived ADRs in `docs/architecture/adrs/archive/` are historical rationale,
not default source-of-truth. Open them only when you need decision context,
trade-offs, or rejected alternatives.

If a contract document and an ADR disagree on fields, topics, tables, or schema
shape, the contract document wins and the living docs or decision register need
a follow-up update.

## Compatibility Rules

Do not rename these without an explicit migration plan and user approval:

- Python packages/imports/entrypoints: `edge_telemetry_agent`, `idp_config_registry`,
  `idp_telemetry_store`, `edge-telemetry-agent`, `idp-config-registry`, `idp-telemetry-store`.
- Docker Compose services, image names, and the compose project name.
- MQTT topic tree `idp/v1/...`.
- Kafka topics and message ids with `idp.*`.
- ClickHouse table/view names and migration filenames.
- Contract ids under `docs/contracts/`.

`idp.*` is a stable wire prefix. It is not a reason to reintroduce the
old product boundary name.

## Working Rules

- Keep changes scoped to the requested module and ownership boundary.
- Never revert unrelated user changes in a dirty worktree.
- Do not use destructive git commands unless the user explicitly asks.
- Prefer `rg` / `rg --files` for search.
- Use `apply_patch` for manual edits.
- Update docs/contracts/C4 when behavior, boundaries, deployment paths, or
  public interfaces change.
- Do not add a new runtime module for Alarm Management until the alarm use cases
  are selected.
- For external libraries or service APIs, verify current docs before changing
  version-sensitive code.

## Repository Map

- `apps/edge_telemetry_agent/`: Edge Telemetry Agent runtime.
- `apps/idp_config_registry/`: Industrial Data Platform Config Registry.
- `apps/knx_demo/`: KNX demo utilities, not a production module.
- `libs/knx_project_parser/`: ETS `.knxproj` parsing library.
- `libs/idp_demo_stack/`: demo and integration glue, not a production module.
- `tools/idp_telemetry_store/`: Telemetry Store migration and load-PoC CLI.
- `infra/local/`: local Industrial Data Platform stack and Web Monitoring
  surface.
- `arch/`: LikeC4 architecture model and generated site tooling.
- `docs/contracts/`: canonical data and storage contracts.
- `docs/architecture/`: architecture docs, decision register, ADR archive,
  glossary, and open questions.
- `docs-site/`: internal Starlight documentation site over curated repo docs.
- `docs/agents/`: agent workflows, roles, templates, and module map.

## Validation Matrix

- Python package change: run the package test command from
  `docs/agents/module-map.yaml`; add integration tests when the data path is
  affected.
- Contract change: validate affected tests and update docs under
  `docs/contracts/`; breaking changes need a new contract version.
- C4 change: run `cd arch && npm run validate`.
- Local infra change: run `docker compose -f infra/local/compose.yaml config
  --quiet`; run relevant integration tests.
- Agent/docs only: run `git diff --check`, parse
  `docs/agents/module-map.yaml`, build `docs-site`, and verify links/references
  with `rg`.

## Agent Workflow

For larger work, use `docs/agents/workflows/task-flow.md` and the role
prompts in `docs/agents/roles/`. Local scratch runs may live under `.local/`,
which is intentionally ignored by git.
