from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from idp_config_registry.application.config_defaults import (
    normalize_acquisition_settings,
    normalize_publish_settings,
)
from idp_config_registry.application.errors import (
    AgentNotFoundError,
    ConfigRenderError,
    DuplicateConfigOutboxRecordError,
    DuplicateConfigRevisionError,
)
from idp_config_registry.application.ports.config_validation import (
    ConfigPayloadValidator,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import (
    AgentRuntimeConfigRevision,
    ConfigOutboxRecord,
    Point,
    Source,
    SourceConfigRevision,
)


@dataclass(frozen=True)
class RenderAgentRuntimeConfigCommand:
    tenant_id: str
    asset_id: str
    agent_id: str
    config_revision: str
    issued_at: datetime
    source_config_revisions: dict[str, str] | None = None


@dataclass(frozen=True)
class RenderedSourceConfig:
    source_id: str
    source_config_revision: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class RenderedAgentRuntimeConfig:
    agent_runtime_payload: dict[str, Any]
    source_payloads: tuple[RenderedSourceConfig, ...]


class RenderAgentRuntimeConfig:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        validator: ConfigPayloadValidator,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._validator = validator

    async def execute(self, command: RenderAgentRuntimeConfigCommand) -> RenderedAgentRuntimeConfig:
        async with self._unit_of_work as unit_of_work:
            agent = await unit_of_work.agents.get(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            )
            if agent is None:
                raise AgentNotFoundError(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                )
            sources = await unit_of_work.sources.list_for_agent(
                command.tenant_id,
                command.asset_id,
                command.agent_id,
            )
            if not sources:
                raise ConfigRenderError(
                    f"Agent {command.agent_id!r} has no sources to render"
                )

            rendered_sources: list[RenderedSourceConfig] = []
            for source in sources:
                points = await unit_of_work.points.list_for_source(
                    command.tenant_id,
                    command.asset_id,
                    command.agent_id,
                    source.source_id,
                )
                rendered_source = self._render_source(command, source, points)
                self._validator.validate_source_config(rendered_source.payload)
                rendered_sources.append(rendered_source)

        agent_runtime_payload = self._agent_runtime_payload(command, rendered_sources)
        self._validator.validate_agent_runtime_config(agent_runtime_payload)
        return RenderedAgentRuntimeConfig(
            agent_runtime_payload=agent_runtime_payload,
            source_payloads=tuple(rendered_sources),
        )

    def _render_source(
        self,
        command: RenderAgentRuntimeConfigCommand,
        source: Source,
        points: list[Point],
    ) -> RenderedSourceConfig:
        source_config_revision = _source_config_revision(command, source.source_id)
        acquisition_defaults = normalize_acquisition_settings(
            source.acquisition_defaults_json
        )
        publish_defaults = normalize_publish_settings(source.publish_defaults_json)
        payload = {
            "message_type": "idp.edge.source-config.v1",
            "tenant_id": command.tenant_id,
            "asset_id": command.asset_id,
            "agent_id": command.agent_id,
            "config_revision": command.config_revision,
            "source_id": source.source_id,
            "source_config_revision": source_config_revision,
            "source_type": source.source_type,
            "enabled": source.enabled,
            "connection": dict(source.connection_json),
            "acquisition_defaults": acquisition_defaults,
            "publish_defaults": publish_defaults,
            "points": [
                _point_payload(
                    point,
                    acquisition_defaults=acquisition_defaults,
                    publish_defaults=publish_defaults,
                )
                for point in points
                if point.enabled
            ],
        }
        return RenderedSourceConfig(
            source_id=source.source_id,
            source_config_revision=source_config_revision,
            payload=payload,
        )

    def _agent_runtime_payload(
        self,
        command: RenderAgentRuntimeConfigCommand,
        rendered_sources: list[RenderedSourceConfig],
    ) -> dict[str, Any]:
        return {
            "message_type": "idp.edge.agent-runtime-config.v1",
            "tenant_id": command.tenant_id,
            "asset_id": command.asset_id,
            "agent_id": command.agent_id,
            "config_revision": command.config_revision,
            "issued_at": _format_datetime(command.issued_at),
            "sources": [
                {
                    "source_id": rendered_source.source_id,
                    "source_config_revision": (
                        rendered_source.source_config_revision
                    ),
                    "enabled": bool(rendered_source.payload["enabled"]),
                }
                for rendered_source in rendered_sources
            ],
        }


def _source_config_revision(
    command: RenderAgentRuntimeConfigCommand,
    source_id: str,
) -> str:
    if command.source_config_revisions is not None:
        revision = command.source_config_revisions.get(source_id)
        if revision is None:
            raise ConfigRenderError(
                f"Missing source_config_revision for source {source_id!r}"
            )
        return revision
    return f"{command.config_revision}-{source_id}"


def _point_payload(
    point: Point,
    *,
    acquisition_defaults: dict[str, Any],
    publish_defaults: dict[str, Any],
) -> dict[str, Any]:
    publish_settings = _settings_with_defaults(point.publish_json, publish_defaults)
    if point.signal_type.value == "command":
        publish_settings = {**publish_settings, "enabled": False}
    return {
        "point_key": point.point_key,
        "point_ref": point.point_ref,
        "name": point.name,
        "description": point.description,
        "value_type": point.value_type.value,
        "value_model": point.value_model,
        "signal_type": point.signal_type.value,
        "unit": point.unit,
        "acquisition": _settings_with_defaults(point.acquisition_json, acquisition_defaults),
        "publish": publish_settings,
        "tags": dict(point.tags_json),
    }


def _settings_with_defaults(
    value: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    return {**defaults, **value}


def _format_datetime(value: datetime) -> str:
    utc_value = value
    if utc_value.tzinfo is None:
        utc_value = utc_value.replace(tzinfo=UTC)
    utc_value = utc_value.astimezone(UTC).replace(microsecond=0)
    return utc_value.isoformat().replace("+00:00", "Z")


class StoreRenderedAgentRuntimeConfig:
    def __init__(
        self,
        unit_of_work: UnitOfWork,
        validator: ConfigPayloadValidator,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._validator = validator

    async def execute(self, rendered: RenderedAgentRuntimeConfig) -> AgentRuntimeConfigRevision:
        agent_runtime_payload = rendered.agent_runtime_payload
        self._validator.validate_agent_runtime_config(agent_runtime_payload)
        for source in rendered.source_payloads:
            self._validator.validate_source_config(source.payload)

        agent_runtime_revision = _agent_runtime_revision_from_payload(
            agent_runtime_payload
        )
        source_revisions = [
            _source_revision_from_payload(
                source.payload,
                issued_at=agent_runtime_revision.issued_at,
            )
            for source in rendered.source_payloads
        ]
        outbox_records = _outbox_records_for_rendered_config(rendered)
        for outbox_record in outbox_records:
            self._validator.validate_config_delivery(outbox_record.payload_json)

        async with self._unit_of_work as unit_of_work:
            if (
                await unit_of_work.agent_runtime_config_revisions.get(
                    agent_runtime_revision.tenant_id,
                    agent_runtime_revision.asset_id,
                    agent_runtime_revision.agent_id,
                    agent_runtime_revision.config_revision,
                )
                is not None
            ):
                raise DuplicateConfigRevisionError(
                    agent_runtime_revision.tenant_id,
                    agent_runtime_revision.asset_id,
                    agent_runtime_revision.agent_id,
                    agent_runtime_revision.config_revision,
                )
            await unit_of_work.agent_runtime_config_revisions.add(
                agent_runtime_revision
            )
            for source_revision in source_revisions:
                await unit_of_work.source_config_revisions.add(source_revision)
            for outbox_record in outbox_records:
                if (
                    await unit_of_work.config_outbox.get_by_idempotency_key(
                        outbox_record.idempotency_key
                    )
                    is not None
                ):
                    raise DuplicateConfigOutboxRecordError(
                        outbox_record.idempotency_key
                    )
                await unit_of_work.config_outbox.add(outbox_record)
            await unit_of_work.commit()

        return agent_runtime_revision


def _agent_runtime_revision_from_payload(
    payload: dict[str, Any],
) -> AgentRuntimeConfigRevision:
    return AgentRuntimeConfigRevision(
        tenant_id=str(payload["tenant_id"]),
        asset_id=str(payload["asset_id"]),
        agent_id=str(payload["agent_id"]),
        config_revision=str(payload["config_revision"]),
        issued_at=_parse_datetime(str(payload["issued_at"])),
        agent_runtime_payload_json=dict(payload),
    )


def _source_revision_from_payload(
    payload: dict[str, Any],
    *,
    issued_at: datetime,
) -> SourceConfigRevision:
    return SourceConfigRevision(
        tenant_id=str(payload["tenant_id"]),
        asset_id=str(payload["asset_id"]),
        agent_id=str(payload["agent_id"]),
        source_id=str(payload["source_id"]),
        source_config_revision=str(payload["source_config_revision"]),
        config_revision=str(payload["config_revision"]),
        issued_at=issued_at,
        source_payload_json=dict(payload),
    )


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _outbox_records_for_rendered_config(
    rendered: RenderedAgentRuntimeConfig,
) -> list[ConfigOutboxRecord]:
    agent_runtime_payload = rendered.agent_runtime_payload
    tenant_id = str(agent_runtime_payload["tenant_id"])
    asset_id = str(agent_runtime_payload["asset_id"])
    agent_id = str(agent_runtime_payload["agent_id"])
    config_revision = str(agent_runtime_payload["config_revision"])
    issued_at = str(agent_runtime_payload["issued_at"])

    records = [
        ConfigOutboxRecord.new(
            tenant_id=tenant_id,
            idempotency_key=(
                f"{tenant_id}|{asset_id}|{agent_id}|{config_revision}|agent_runtime"
            ),
            asset_id=asset_id,
            agent_id=agent_id,
            config_revision=config_revision,
            config_scope="agent_runtime",
            source_id=None,
            source_config_revision=None,
            kafka_key=f"{tenant_id}|{asset_id}|{agent_id}|agent_runtime",
            payload_json={
                "message_type": "idp.edge.config.delivery.v1",
                "tenant_id": tenant_id,
                "asset_id": asset_id,
                "agent_id": agent_id,
                "config_revision": config_revision,
                "config_scope": "agent_runtime",
                "source_id": None,
                "source_config_revision": None,
                "target_mqtt_topic": f"idp/v1/agents/{agent_id}/config/agent-runtime",
                "mqtt_retain": True,
                "mqtt_qos": 1,
                "operation": "upsert",
                "payload_message_type": "idp.edge.agent-runtime-config.v1",
                "payload": dict(agent_runtime_payload),
                "idempotency_key": (
                    f"{tenant_id}|{asset_id}|{agent_id}|{config_revision}|agent_runtime"
                ),
                "issued_at": issued_at,
            },
        )
    ]

    for rendered_source in rendered.source_payloads:
        source_payload = rendered_source.payload
        source_id = str(source_payload["source_id"])
        source_config_revision = str(source_payload["source_config_revision"])
        config_scope = f"source:{source_id}"
        idempotency_key = (
            f"{tenant_id}|{asset_id}|{agent_id}|{config_revision}|source|{source_id}"
        )
        records.append(
            ConfigOutboxRecord.new(
                tenant_id=tenant_id,
                idempotency_key=idempotency_key,
                asset_id=asset_id,
                agent_id=agent_id,
                config_revision=config_revision,
                config_scope=config_scope,
                source_id=source_id,
                source_config_revision=source_config_revision,
                kafka_key=f"{tenant_id}|{asset_id}|{agent_id}|{config_scope}",
                payload_json={
                    "message_type": "idp.edge.config.delivery.v1",
                    "tenant_id": tenant_id,
                    "asset_id": asset_id,
                    "agent_id": agent_id,
                    "config_revision": config_revision,
                    "config_scope": config_scope,
                    "source_id": source_id,
                    "source_config_revision": source_config_revision,
                    "target_mqtt_topic": (
                        f"idp/v1/agents/{agent_id}/sources/{source_id}/config"
                    ),
                    "mqtt_retain": True,
                    "mqtt_qos": 1,
                    "operation": "upsert",
                    "payload_message_type": "idp.edge.source-config.v1",
                    "payload": dict(source_payload),
                    "idempotency_key": idempotency_key,
                    "issued_at": issued_at,
                },
            )
        )

    return records
