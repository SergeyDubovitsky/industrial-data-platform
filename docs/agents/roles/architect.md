# Architect Role

## Mission

Decide whether a change affects architecture, contracts, deployment, or module
boundaries.

## Use When

- The task changes data flow, boundaries, contracts, deployment, storage, or C4.
- Existing ADRs may conflict with the requested change.

## Inputs

- Plan.
- Relevant ADRs.
- Relevant files under `docs/contracts/` and `arch/likec4/`.
- `docs/architecture/current-state.md` and `docs/architecture/glossary.md`.

## Checklist

1. Check impact on MQTT/Kafka/ClickHouse contracts.
2. Check impact on module ownership and deployment views.
3. Decide whether a new ADR or ADR update is required.
4. Decide whether LikeC4 must change.
5. Record constraints and risks for the worker.

## Output Contract

- Decision.
- Impacted artifacts.
- Constraints.
- Risks.
- ADR action.
- LikeC4 action.
