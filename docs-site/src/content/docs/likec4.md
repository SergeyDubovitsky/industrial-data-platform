---
title: LikeC4
description: Architecture model entrypoint and validation commands.
---

LikeC4 is the source of truth for systems, containers, ownership, dependencies,
and deployment views.

## Entry points

- `arch/README.md`: model layout and commands.
- `arch/likec4/views.c4`: C1 system context.
- `arch/likec4/systems/edge-telemetry-agent/views.c4`: Edge Telemetry Agent C2.
- `arch/likec4/systems/industrial-data-platform/views.c4`: Industrial Data Platform C2.
- `arch/likec4/systems/web-monitoring-module/views.c4`: Web Monitoring Module C2.
- `arch/likec4/systems/alarm-management-module/views.c4`: Alarm Management Module C2.

## Commands

```bash
cd arch
npm run validate
npm run build
```

Run LikeC4 validation when a change affects architecture boundaries, ownership,
deployment paths, or diagrams.
