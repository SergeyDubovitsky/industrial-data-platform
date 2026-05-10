from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Annotated, Any, Mapping, Self, TypeVar

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from edge_telemetry_agent.domain.config import (
    AcquisitionSettings,
    AgentRuntimeConfig,
    BootstrapConfig,
    ConfigurationError,
    DeliverySettings,
    MqttSettings,
    ObservabilitySettings,
    PublishSettings,
    RuntimePoint,
    SourceDefinition,
    SourceRuntimeRef,
    StorageSettings,
    ValueType,
)
from edge_telemetry_agent.infrastructure.mqtt_retained_config import (
    RetainedConfigLoader,
)
from edge_telemetry_agent.modeling import EdgeModel

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
MqttPathId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        strict=True,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,127}$",
    ),
]
MqttTopicRoot = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        strict=True,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,127}(?:/[a-z0-9][a-z0-9_-]{0,127})*$",
    ),
]
StrictNonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
ModelT = TypeVar("ModelT", bound=EdgeModel)
ENV_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigModel(EdgeModel):
    pass


class AcquisitionSettingsModel(ConfigModel):
    listen: StrictBool = True
    read_on_start: StrictBool = False
    periodic_interval_seconds: float | None = None

    @field_validator("periodic_interval_seconds", mode="before")
    @classmethod
    def normalize_periodic_interval(cls, value: Any) -> float | None:
        return _optional_float(value, field_name="periodic_interval_seconds", positive=True)


class PublishSettingsModel(ConfigModel):
    enabled: StrictBool = True
    change_threshold: float | None = None

    @field_validator("change_threshold", mode="before")
    @classmethod
    def normalize_change_threshold(cls, value: Any) -> float | None:
        return _optional_float(value, field_name="change_threshold", positive=False)


class BootstrapMqttSettingsModel(ConfigModel):
    enabled: StrictBool
    version: NonEmptyStr
    broker: NonEmptyStr
    topic_root: MqttTopicRoot
    client_id_prefix: NonEmptyStr
    username_env: str | None = None
    password_env: str | None = None
    qos: StrictInt
    clean_start: StrictBool
    session_expiry_seconds: StrictInt
    telemetry_message_expiry_seconds: StrictInt
    connect_timeout_seconds: StrictInt
    retry_backoff_seconds: list[StrictNonNegativeInt]

    @field_validator("username_env", "password_env", mode="before")
    @classmethod
    def normalize_optional_env_name(cls, value: Any) -> str | None:
        return _optional_string(value)


class DeliverySettingsModel(ConfigModel):
    transport: NonEmptyStr
    mqtt: BootstrapMqttSettingsModel | None = None

    @model_validator(mode="after")
    def validate_selected_transport(self) -> Self:
        if self.transport == "mqtt" and self.mqtt is None:
            raise ValueError("mqtt settings are required when delivery.transport is mqtt")
        return self


class StorageSettingsModel(ConfigModel):
    sqlite_path: NonEmptyStr
    retention_days: StrictInt
    dead_letter_after_attempts: StrictInt


class ObservabilitySettingsModel(ConfigModel):
    log_level: NonEmptyStr
    emit_health_events: StrictBool
    metrics_bind: str | None = None

    @field_validator("metrics_bind", mode="before")
    @classmethod
    def normalize_metrics_bind(cls, value: Any) -> str | None:
        return _optional_string(value)


class BootstrapDocumentModel(ConfigModel):
    agent_id: MqttPathId
    delivery: DeliverySettingsModel
    storage: StorageSettingsModel
    observability: ObservabilitySettingsModel


class RuntimeSourceRefModel(ConfigModel):
    source_id: MqttPathId
    source_config_revision: NonEmptyStr
    enabled: StrictBool


class AgentRuntimeConfigPayloadModel(ConfigModel):
    message_type: str
    tenant_id: NonEmptyStr
    asset_id: MqttPathId
    agent_id: MqttPathId
    config_revision: NonEmptyStr
    issued_at: NonEmptyStr
    sources: list[RuntimeSourceRefModel]

    @model_validator(mode="after")
    def validate_message_type(self) -> Self:
        if self.message_type != "idp.edge.agent-runtime-config.v1":
            raise ValueError("message_type must be idp.edge.agent-runtime-config.v1")
        return self


class SourcePointModel(ConfigModel):
    point_key: NonEmptyStr
    point_ref: NonEmptyStr
    name: NonEmptyStr
    description: str | None = None
    value_type: ValueType
    value_model: NonEmptyStr
    signal_type: str
    unit: str | None = None
    acquisition: AcquisitionSettingsModel
    publish: PublishSettingsModel
    tags: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)

    @field_validator("description", "unit", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        return _optional_string(value)

    @model_validator(mode="after")
    def validate_point(self) -> Self:
        if self.point_key != _point_key_from_ref(self.point_ref):
            raise ValueError("point_key must be percent-encoded point_ref")
        if self.value_type != "number" and self.publish.change_threshold is not None:
            raise ValueError("change_threshold is only allowed for number points")
        return self


class SourceConfigPayloadModel(ConfigModel):
    message_type: str
    tenant_id: NonEmptyStr
    asset_id: MqttPathId
    agent_id: MqttPathId
    config_revision: NonEmptyStr
    source_id: MqttPathId
    source_config_revision: NonEmptyStr
    source_type: NonEmptyStr
    enabled: StrictBool
    connection: dict[NonEmptyStr, Any]
    acquisition_defaults: AcquisitionSettingsModel
    publish_defaults: PublishSettingsModel
    points: list[SourcePointModel]

    @model_validator(mode="after")
    def validate_message_type(self) -> Self:
        if self.message_type != "idp.edge.source-config.v1":
            raise ValueError("message_type must be idp.edge.source-config.v1")
        return self


def load_bootstrap_config(bootstrap_config_path: Path) -> BootstrapConfig:
    payload = _load_document(bootstrap_config_path)
    document = _validate_model(BootstrapDocumentModel, payload, "bootstrap config")
    return BootstrapConfig(
        agent_id=document.agent_id,
        delivery=_to_delivery_settings(document.delivery),
        storage=_to_storage_settings(document.storage),
        observability=_to_observability_settings(document.observability),
    )


def load_agent_runtime_config(bootstrap_config_path: Path) -> AgentRuntimeConfig:
    bootstrap = load_bootstrap_config(bootstrap_config_path)
    mqtt = bootstrap.delivery.mqtt
    if mqtt is None or not mqtt.enabled:
        raise ConfigurationError("MQTT delivery settings are not configured or disabled")
    retained = RetainedConfigLoader(mqtt, agent_id=bootstrap.agent_id).load()
    return build_agent_runtime_config(
        bootstrap_data=_load_document(bootstrap_config_path),
        agent_runtime_data=retained.agent_runtime_config,
        source_documents=list(retained.source_configs.values()),
    )


def build_agent_runtime_config(
    *,
    bootstrap_data: Mapping[str, object],
    agent_runtime_data: Mapping[str, object],
    source_documents: list[Mapping[str, object]],
) -> AgentRuntimeConfig:
    bootstrap = _validate_model(BootstrapDocumentModel, bootstrap_data, "bootstrap config")
    agent_runtime_payload = _validate_model(
        AgentRuntimeConfigPayloadModel,
        agent_runtime_data,
        "agent runtime config",
    )
    if agent_runtime_payload.agent_id != bootstrap.agent_id:
        raise ConfigurationError(
            "Agent runtime config agent_id does not match bootstrap agent_id"
        )

    source_refs = {
        item.source_id: SourceRuntimeRef(
            source_id=item.source_id,
            source_config_revision=item.source_config_revision,
            enabled=item.enabled,
        )
        for item in agent_runtime_payload.sources
    }
    source_payloads: dict[str, SourceConfigPayloadModel] = {}
    for index, raw_source in enumerate(source_documents):
        source_payload = _validate_model(
            SourceConfigPayloadModel,
            raw_source,
            f"source config #{index}",
        )
        if source_payload.source_id in source_payloads:
            raise ConfigurationError(f"Duplicate source_id: {source_payload.source_id}")
        source_payloads[source_payload.source_id] = source_payload

    missing_source_ids = sorted(set(source_refs) - set(source_payloads))
    if missing_source_ids:
        raise ConfigurationError(
            "Missing retained source config for source_id(s): "
            + ", ".join(missing_source_ids)
        )

    sources: dict[str, SourceDefinition] = {}
    points: dict[tuple[str, str], RuntimePoint] = {}
    for source_id, source_ref in source_refs.items():
        source_payload = source_payloads[source_id]
        _validate_source_matches_agent_runtime(
            agent_runtime_payload,
            source_ref,
            source_payload,
        )

        source = SourceDefinition(
            source_id=source_payload.source_id,
            source_config_revision=source_payload.source_config_revision,
            source_type=source_payload.source_type,
            enabled=source_payload.enabled,
            connection=dict(source_payload.connection),
            acquisition_defaults=_to_acquisition_settings(source_payload.acquisition_defaults),
            publish_defaults=_to_publish_settings(source_payload.publish_defaults),
        )
        sources[source_id] = source
        if not source.enabled:
            continue

        point_names: set[str] = set()
        point_refs: set[str] = set()
        for point_model in source_payload.points:
            if point_model.point_ref in point_refs:
                raise ConfigurationError(
                    f"Duplicate point_ref for source {source_id}: {point_model.point_ref}"
                )
            if point_model.name in point_names:
                raise ConfigurationError(
                    f"Duplicate point name for source {source_id}: {point_model.name}"
                )
            point_refs.add(point_model.point_ref)
            point_names.add(point_model.name)
            runtime_point = RuntimePoint(
                source_id=source_id,
                source_type=source.source_type,
                source_config_revision=source.source_config_revision,
                point_key=point_model.point_key,
                point_ref=point_model.point_ref,
                name=point_model.name,
                description=point_model.description,
                value_type=point_model.value_type,
                value_model=point_model.value_model,
                signal_type=point_model.signal_type,
                unit=point_model.unit,
                acquisition=_to_acquisition_settings(point_model.acquisition),
                publish=_to_publish_settings(point_model.publish),
                tags=dict(point_model.tags),
            )
            points[(source_id, runtime_point.point_ref)] = runtime_point

    return AgentRuntimeConfig(
        tenant_id=agent_runtime_payload.tenant_id,
        asset_id=agent_runtime_payload.asset_id,
        agent_id=agent_runtime_payload.agent_id,
        config_revision=agent_runtime_payload.config_revision,
        delivery=_to_delivery_settings(bootstrap.delivery),
        storage=_to_storage_settings(bootstrap.storage),
        observability=_to_observability_settings(bootstrap.observability),
        sources=sources,
        source_refs=source_refs,
        points=points,
    )


def _validate_source_matches_agent_runtime(
    agent_runtime_payload: AgentRuntimeConfigPayloadModel,
    source_ref: SourceRuntimeRef,
    source_payload: SourceConfigPayloadModel,
) -> None:
    if source_payload.tenant_id != agent_runtime_payload.tenant_id:
        raise ConfigurationError(
            f"Source {source_payload.source_id} tenant_id does not match agent runtime config"
        )
    if source_payload.asset_id != agent_runtime_payload.asset_id:
        raise ConfigurationError(
            f"Source {source_payload.source_id} asset_id does not match agent runtime config"
        )
    if source_payload.agent_id != agent_runtime_payload.agent_id:
        raise ConfigurationError(
            f"Source {source_payload.source_id} agent_id does not match agent runtime config"
        )
    if source_payload.config_revision != agent_runtime_payload.config_revision:
        raise ConfigurationError(
            f"Source {source_payload.source_id} config_revision does not match agent runtime config"
        )
    if source_payload.source_config_revision != source_ref.source_config_revision:
        raise ConfigurationError(
            f"Source {source_payload.source_id} source_config_revision does not match agent runtime config"
        )
    if source_payload.enabled != source_ref.enabled:
        raise ConfigurationError(
            f"Source {source_payload.source_id} enabled flag does not match agent runtime config"
        )


def _load_document(path: Path) -> object:
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as handle:
            return _expand_env_placeholders(json.load(handle), source=path)
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to load YAML config files. "
            "Add pyyaml to the edge_telemetry_agent project dependencies before using YAML configs."
        )
    with path.open("r", encoding="utf-8") as handle:
        return _expand_env_placeholders(yaml.safe_load(handle), source=path)


def _to_delivery_settings(model: DeliverySettingsModel) -> DeliverySettings:
    mqtt = _to_mqtt_settings(model.mqtt) if model.mqtt is not None else None
    return DeliverySettings(transport=model.transport, mqtt=mqtt)


def _to_mqtt_settings(model: BootstrapMqttSettingsModel | None) -> MqttSettings | None:
    if model is None:
        return None
    return MqttSettings(
        enabled=model.enabled,
        version=model.version,
        broker=model.broker,
        topic_root=model.topic_root,
        client_id_prefix=model.client_id_prefix,
        username_env=model.username_env,
        password_env=model.password_env,
        qos=model.qos,
        clean_start=model.clean_start,
        session_expiry_seconds=model.session_expiry_seconds,
        telemetry_message_expiry_seconds=model.telemetry_message_expiry_seconds,
        connect_timeout_seconds=model.connect_timeout_seconds,
        retry_backoff_seconds=tuple(model.retry_backoff_seconds),
    )


def _to_storage_settings(model: StorageSettingsModel) -> StorageSettings:
    return StorageSettings(
        sqlite_path=Path(model.sqlite_path),
        retention_days=model.retention_days,
        dead_letter_after_attempts=model.dead_letter_after_attempts,
    )


def _to_observability_settings(model: ObservabilitySettingsModel) -> ObservabilitySettings:
    return ObservabilitySettings(
        log_level=model.log_level,
        emit_health_events=model.emit_health_events,
        metrics_bind=model.metrics_bind,
    )


def _to_acquisition_settings(model: AcquisitionSettingsModel) -> AcquisitionSettings:
    return AcquisitionSettings(
        listen=model.listen,
        read_on_start=model.read_on_start,
        periodic_interval_seconds=model.periodic_interval_seconds,
    )


def _to_publish_settings(model: PublishSettingsModel) -> PublishSettings:
    return PublishSettings(
        enabled=model.enabled,
        change_threshold=model.change_threshold,
    )


def _validate_model(model_type: type[ModelT], raw: object, context: str) -> ModelT:
    try:
        return model_type.model_validate(raw)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        location = ".".join(str(part) for part in first_error["loc"])
        message = first_error["msg"]
        detail = f"{context}.{location} {message}" if location else f"{context} {message}"
        raise ConfigurationError(detail) from exc


def _optional_float(value: Any, *, field_name: str, positive: bool) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number or null")
    normalized = float(value)
    if positive and normalized <= 0:
        raise ValueError(f"{field_name} must be greater than 0")
    if not positive and normalized < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0")
    return normalized


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("must be a string or null")
    stripped = value.strip()
    return stripped or None


def _expand_env_placeholders(value: object, *, source: Path) -> object:
    if isinstance(value, str):
        return ENV_PLACEHOLDER_PATTERN.sub(
            lambda match: _required_env_value(match.group(1), source=source),
            value,
        )
    if isinstance(value, list):
        return [_expand_env_placeholders(item, source=source) for item in value]
    if isinstance(value, dict):
        return {
            key: _expand_env_placeholders(item, source=source)
            for key, item in value.items()
        }
    return value


def _required_env_value(env_name: str, *, source: Path) -> str:
    value = os.getenv(env_name)
    if value is None:
        raise ConfigurationError(
            f"Environment variable {env_name!r} referenced in {source} is not set"
        )
    return value


def _point_key_from_ref(point_ref: str) -> str:
    from urllib.parse import quote

    return quote(point_ref, safe="")
