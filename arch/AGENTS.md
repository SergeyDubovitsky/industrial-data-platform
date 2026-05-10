# LikeC4 Architecture Guide

Scope: `arch/`.

`arch/likec4/` is the source of truth for C4 architecture and deployment views.

## Do

- Use the `likec4-dsl` skill for non-trivial C4 edits.
- Keep developed systems aligned with `Industrial Data Platform`,
  `Edge Telemetry Agent`, `Web Monitoring Module`, and `Alarm Management Module`.
- Keep one container file per container under the owning system.
- Update architecture docs or ADRs when C4 reflects a new decision.

## Do Not

- Do not reintroduce `Monitoring & Alarm Platform` as the central system name.
- Do not use C4 as the only source for field-level contract details.
- Do not edit generated `arch/dist/` as source.

## Validation

- `cd arch && npm run validate`
- For published site changes: `cd arch && npm run build`
