# Demo Stand Environment

Этот каталог хранит production-like профиль demo-стенда для сценария,
в котором `Edge Telemetry Agent` работает в локальной сети объекта рядом с
`KNX/IP` роутером.

Чувствительные endpoint-данные для `edge_telemetry_agent` вынесены в общий root-level
`.env`, поэтому versioned YAML здесь содержит только структуру и ссылки на
переменные окружения.

Текущая структура:

```text
environments/demo-stand/
├── README.md
└── edge_telemetry_agent/
    ├── bootstrap.yaml
    └── config.bundle.yaml
```

Этот профиль рассчитан на локальный dev-стек из `infra/local/`:

- `broker: mqtt://localhost:1883`
- локальный state агента: `.local/demo-stand/edge-telemetry-agent/*`

Для текущего удаленного workstation-based сценария используйте отдельный профиль
`environments/demo-stand-remote/edge_telemetry_agent/`.

Проверка bootstrap + retained config path после demo config seed:

```bash
uv run --env-file .env --package edge-telemetry-agent edge-telemetry-agent check-config \
  --bootstrap-config environments/demo-stand/edge_telemetry_agent/bootstrap.yaml
```

Для seed config через `Config Registry API -> outbox worker -> Kafka` используйте:

```bash
uv run --env-file .env --package idp-demo-stack publish-edge-demo \
  --bundle-config environments/demo-stand/edge_telemetry_agent/config.bundle.yaml
```

Секреты и machine-local overrides сюда не коммитятся.
