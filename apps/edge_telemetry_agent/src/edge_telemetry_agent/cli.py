from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from edge_telemetry_agent.application.configuration import load_agent_runtime_config
from edge_telemetry_agent.application.delivery import DeliveryWorker
from edge_telemetry_agent.application.processing import ObservationProcessor
from edge_telemetry_agent.domain.config import (
    AgentRuntimeConfig,
    ConfigurationError,
    RuntimePoint,
)
from edge_telemetry_agent.domain.events import Observation, ScalarValue
from edge_telemetry_agent.infrastructure.mqtt_publisher import connect_mqtt_publisher
from edge_telemetry_agent.infrastructure.sqlite_outbox import SQLiteOutbox
from edge_telemetry_agent.infrastructure.sqlite_point_state import SQLitePointStateCache


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except (ConfigurationError, FileNotFoundError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edge-telemetry-agent",
        description="CLI for the edge telemetry runtime",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_config = subparsers.add_parser(
        "check-config",
        help="Load bootstrap config and validate retained agent runtime/source configs",
    )
    _add_bootstrap_config_argument(check_config)
    check_config.set_defaults(handler=_handle_check_config)

    show_config = subparsers.add_parser(
        "show-config",
        help="Print a normalized agent runtime configuration summary",
    )
    _add_bootstrap_config_argument(show_config)
    show_config.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for the summary",
    )
    show_config.set_defaults(handler=_handle_show_config)

    enqueue_demo_event = subparsers.add_parser(
        "enqueue-demo-event",
        help="Create one synthetic telemetry event and append it to the SQLite outbox",
    )
    _add_bootstrap_config_argument(enqueue_demo_event)
    enqueue_demo_event.add_argument(
        "--source-id",
        default=None,
        help="Source id; defaults to the first source that has publish-enabled points",
    )
    enqueue_demo_event.add_argument(
        "--point-ref",
        default=None,
        help="Point reference; defaults to the first publish-enabled point for source",
    )
    enqueue_demo_event.add_argument(
        "--value",
        default=None,
        help="Telemetry value; defaults to a type-specific demo value",
    )
    enqueue_demo_event.set_defaults(handler=_handle_enqueue_demo_event)

    deliver_once = subparsers.add_parser(
        "deliver-once",
        help="Publish one batch from the SQLite outbox to the configured MQTT broker",
    )
    _add_bootstrap_config_argument(deliver_once)
    deliver_once.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of pending outbox records to reserve",
    )
    deliver_once.add_argument(
        "--lease-seconds",
        type=int,
        default=60,
        help="Lease duration for reserved outbox records",
    )
    deliver_once.set_defaults(handler=_handle_deliver_once)

    return parser


def _add_bootstrap_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--bootstrap-config",
        type=Path,
        required=True,
        help="Path to edge.bootstrap-config.v1 YAML or JSON file",
    )


def _handle_check_config(args: argparse.Namespace) -> int:
    runtime = load_agent_runtime_config(args.bootstrap_config)
    summary = _runtime_summary(runtime, args.bootstrap_config)
    print(
        "Configuration OK: "
        f"tenant_id={summary['tenant_id']} "
        f"asset_id={summary['asset_id']} "
        f"agent_id={summary['agent_id']} "
        f"sources={summary['source_count']} "
        f"points={summary['point_count']} "
        f"bootstrap_config={summary['bootstrap_config']}"
    )
    return 0


def _handle_show_config(args: argparse.Namespace) -> int:
    runtime = load_agent_runtime_config(args.bootstrap_config)
    summary = _runtime_summary(runtime, args.bootstrap_config)
    if args.format == "json":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(_render_text_summary(summary))
    return 0


def _handle_enqueue_demo_event(args: argparse.Namespace) -> int:
    runtime = load_agent_runtime_config(args.bootstrap_config)
    point = _select_demo_point(runtime, source_id=args.source_id, point_ref=args.point_ref)
    value = _coerce_demo_value(args.value, value_type=point.value_type)
    state_cache = SQLitePointStateCache(runtime.storage.sqlite_path)
    state_cache.initialize()
    processor = ObservationProcessor(
        runtime,
        agent_id=runtime.agent_id,
        state_store=state_cache,
    )
    result = processor.process(
        Observation(
            source_id=point.source_id,
            point_ref=point.point_ref,
            observation_mode="listen",
            value=value,
            value_raw=None if value is None else str(value),
        )
    )
    if result.event is None:
        raise RuntimeError(
            "Demo observation was not publishable"
            + (f": {result.suppressed_reason}" if result.suppressed_reason else "")
        )

    outbox = SQLiteOutbox(runtime.storage.sqlite_path)
    outbox.initialize()
    record_id = outbox.append(result.event)
    print(
        "Enqueued demo event: "
        f"record_id={record_id} "
        f"event_id={result.event.event_id} "
        f"source_id={point.source_id} "
        f"point_ref={point.point_ref}"
    )
    return 0


def _handle_deliver_once(args: argparse.Namespace) -> int:
    runtime = load_agent_runtime_config(args.bootstrap_config)
    mqtt = runtime.delivery.mqtt
    if mqtt is None or not mqtt.enabled:
        raise RuntimeError("MQTT delivery settings are not configured or disabled")

    outbox = SQLiteOutbox(runtime.storage.sqlite_path)
    outbox.initialize()
    publisher = connect_mqtt_publisher(mqtt, agent_id=runtime.agent_id)
    worker = DeliveryWorker(
        runtime_config=runtime,
        agent_id=runtime.agent_id,
        outbox=outbox,
        publisher=publisher,
    )
    try:
        result = worker.deliver_once(limit=args.limit, lease_seconds=args.lease_seconds)
    finally:
        publisher.close()

    print(
        "Delivery run: "
        f"reserved={result.reserved_count} "
        f"published={result.published_count} "
        f"retry={result.retry_count} "
        f"dead_letter={result.dead_letter_count}"
    )
    return 0


def _runtime_summary(
    runtime: AgentRuntimeConfig,
    bootstrap_config: Path,
) -> dict[str, Any]:
    points = sorted(runtime.points.values(), key=lambda point: (point.source_id, point.point_ref))
    return {
        "bootstrap_config": str(bootstrap_config.resolve()),
        "tenant_id": runtime.tenant_id,
        "asset_id": runtime.asset_id,
        "agent_id": runtime.agent_id,
        "config_revision": runtime.config_revision,
        "transport": runtime.delivery.transport,
        "source_count": len(runtime.sources),
        "point_count": len(runtime.points),
        "sources": [
            {
                "source_id": source.source_id,
                "source_type": source.source_type,
                "source_config_revision": source.source_config_revision,
                "enabled": source.enabled,
            }
            for source in sorted(runtime.sources.values(), key=lambda source: source.source_id)
        ],
        "points": [
            {
                "source_id": point.source_id,
                "source_config_revision": point.source_config_revision,
                "point_key": point.point_key,
                "point_ref": point.point_ref,
                "name": point.name,
                "signal_type": point.signal_type,
                "value_type": point.value_type,
                "value_model": point.value_model,
                "publish_enabled": point.publish.enabled,
            }
            for point in points
        ],
    }


def _render_text_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"Bootstrap config: {summary['bootstrap_config']}",
        f"Tenant ID: {summary['tenant_id']}",
        f"Object ID: {summary['asset_id']}",
        f"Agent ID: {summary['agent_id']}",
        f"Config revision: {summary['config_revision']}",
        f"Transport: {summary['transport']}",
        f"Sources: {summary['source_count']}",
        f"Points: {summary['point_count']}",
    ]
    for source in summary["sources"]:
        lines.append(
            "- source "
            f"{source['source_id']} "
            f"type={source['source_type']} "
            f"source_config_revision={source['source_config_revision']} "
            f"enabled={source['enabled']}"
        )
    for point in summary["points"]:
        lines.append(
            "- point "
            f"{point['source_id']}:{point['point_ref']} "
            f"key={point['point_key']} "
            f"name={point['name']} "
            f"signal_type={point['signal_type']} "
            f"value_model={point['value_model']} "
            f"source_config_revision={point['source_config_revision']} "
            f"publish_enabled={point['publish_enabled']}"
        )
    return "\n".join(lines)


def _select_demo_point(
    runtime: AgentRuntimeConfig,
    *,
    source_id: str | None,
    point_ref: str | None,
) -> RuntimePoint:
    candidates = [
        point
        for point in sorted(
            runtime.points.values(),
            key=lambda item: (item.source_id, item.point_ref),
        )
        if point.publish.enabled
        and (source_id is None or point.source_id == source_id)
        and (point_ref is None or point.point_ref == point_ref)
    ]
    if not candidates:
        raise RuntimeError(
            "No publish-enabled points matched the requested source/point selection"
        )
    return candidates[0]


def _coerce_demo_value(raw_value: str | None, *, value_type: str) -> ScalarValue:
    if raw_value is None:
        defaults: dict[str, ScalarValue] = {
            "boolean": True,
            "number": 23.5,
            "string": "demo",
        }
        return defaults[value_type]
    if value_type == "boolean":
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "on", "yes"}:
            return True
        if normalized in {"0", "false", "off", "no"}:
            return False
        raise RuntimeError(f"Cannot parse boolean demo value from {raw_value!r}")
    if value_type == "number":
        try:
            return float(raw_value)
        except ValueError as exc:
            raise RuntimeError(f"Cannot parse number demo value from {raw_value!r}") from exc
    return raw_value
