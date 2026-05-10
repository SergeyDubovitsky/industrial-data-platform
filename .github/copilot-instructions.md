# GitHub Copilot Repository Instructions

Use `AGENTS.md` as the canonical repository guide.

Key rules:

- Preserve compatibility identifiers: Python package names, CLI entrypoints,
  Docker services/images, MQTT `idp/v1`, Kafka `idp.*`, ClickHouse tables,
  and contract ids.
- Treat `docs/contracts/` as the source of truth for wire/storage contracts.
- Treat `arch/likec4/` as the source of truth for C4 architecture.
- Treat `docs/agents/module-map.yaml` as the ownership and validation map.
- Keep changes scoped to the module or path being edited.
