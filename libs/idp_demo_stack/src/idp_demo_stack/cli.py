from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse

from idp_demo_stack.bundle import load_bundle
from idp_demo_stack.config_registry_client import publish_bundle_via_idp_config_registry
from idp_demo_stack.kafka_publisher import connect_kafka_publisher
from idp_demo_stack.models import (
    BrokerConfig,
    ConfigRegistryConfig,
    DemoSettings,
    KafkaConfig,
    TopicScope,
    WaveConfig,
)
from idp_demo_stack.publisher import connect_publisher
from idp_demo_stack.retained_config import wait_for_retained_config_projection
from idp_demo_stack.runtime import SystemRuntime
from idp_demo_stack.scenario import config_delivery_records, run_demo


def parse_args() -> argparse.Namespace:
    default_broker = os.environ.get("MQTT_BROKER", "mqtt://localhost:1883")
    default_kafka = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    default_config_registry_url = os.environ.get(
        "CONFIG_REGISTRY_URL",
        "http://localhost:8000",
    )
    default_username = os.environ.get("MQTT_USERNAME")
    default_password = os.environ.get("MQTT_PASSWORD")

    parser = argparse.ArgumentParser(
        description=(
            "Seed demo edge config through Config Registry API and publish "
            "telemetry to MQTT."
        ),
    )
    parser.add_argument(
        "--bundle-config",
        type=Path,
        required=True,
        help="Path to config.bundle.yaml or JSON authoring bundle.",
    )
    parser.add_argument(
        "--broker",
        default=default_broker,
        help=(
            "MQTT broker URI, for example mqtt://localhost:1883. "
            "Defaults to MQTT_BROKER or mqtt://localhost:1883."
        ),
    )
    parser.add_argument(
        "--username",
        default=default_username,
        help=(
            "MQTT username. Defaults to MQTT_USERNAME. "
            "If still omitted, connects without authentication."
        ),
    )
    parser.add_argument(
        "--password",
        default=default_password,
        help=(
            "MQTT password. Defaults to MQTT_PASSWORD. "
            "If still omitted, connects without authentication."
        ),
    )
    parser.add_argument(
        "--topic-root",
        default="idp/v1",
        help="MQTT topic root for projected retained config and telemetry topics.",
    )
    parser.add_argument(
        "--source-id",
        default=None,
        help="Source identifier from the bundle to use for live telemetry and status.",
    )
    parser.add_argument(
        "--client-id",
        default="manual-edge-demo-publisher",
        help="MQTT client id for this generator process.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=2.0,
        help="Delay between publish cycles.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of publish cycles. 0 means run forever.",
    )
    parser.add_argument(
        "--temperature-base",
        type=float,
        default=23.0,
        help="Base temperature value in Celsius.",
    )
    parser.add_argument(
        "--temperature-amplitude",
        type=float,
        default=1.8,
        help="Sine-wave amplitude for generated temperature values.",
    )
    parser.add_argument(
        "--temperature-period",
        type=float,
        default=8.0,
        help="Number of cycles in one temperature wave period.",
    )
    parser.add_argument(
        "--kafka-bootstrap-servers",
        default=default_kafka,
        help=(
            "Kafka bootstrap servers for config delivery records. "
            "Defaults to KAFKA_BOOTSTRAP_SERVERS or localhost:19092."
        ),
    )
    parser.add_argument(
        "--idp-config-registry-url",
        dest="config_registry_url",
        default=default_config_registry_url,
        help=(
            "Config Registry API base URL. Defaults to CONFIG_REGISTRY_URL "
            "or http://localhost:8000."
        ),
    )
    parser.add_argument(
        "--kafka-client-id",
        default="manual-edge-demo-config-publisher",
        help="Kafka producer client id for config delivery records.",
    )
    parser.add_argument(
        "--config-delivery",
        choices=("api", "kafka", "mqtt", "none"),
        default="api",
        help=(
            "How to seed runtime/source config. Default api imports the bundle "
            "through Config Registry API and relies on the outbox worker."
        ),
    )
    parser.add_argument(
        "--config-projection-timeout-seconds",
        type=float,
        default=15.0,
        help=(
            "When --config-delivery api or kafka is used, wait this long for "
            "retained runtime/source configs to appear in MQTT before telemetry "
            "starts. 0 disables waiting."
        ),
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Deprecated shortcut for --config-delivery none.",
    )
    parser.add_argument(
        "--no-status",
        action="store_true",
        help="Do not publish retained source status and agent LWT records.",
    )
    parser.add_argument(
        "--retained-refresh-seconds",
        type=float,
        default=30.0,
        help=(
            "Republish MQTT retained config only in --config-delivery mqtt mode; "
            "status refresh still uses this interval. 0 disables refresh."
        ),
    )
    return parser.parse_args()


def parse_broker(uri: str) -> BrokerConfig:
    parsed = urlparse(uri if "://" in uri else f"mqtt://{uri}")
    if parsed.scheme not in {"mqtt", "tcp"}:
        raise ValueError(
            f"Unsupported broker URI scheme: {parsed.scheme or '<empty>'}. "
            "Use mqtt://host:port or tcp://host:port."
        )
    if parsed.hostname is None:
        raise ValueError(f"Broker host is missing in URI: {uri}")
    return BrokerConfig(host=parsed.hostname, port=parsed.port or 1883)


def settings_from_args(args: argparse.Namespace) -> DemoSettings:
    if args.username and not args.password:
        raise ValueError("--password is required when --username is set")
    if args.interval_seconds < 0:
        raise ValueError("--interval-seconds must be non-negative")
    if args.count < 0:
        raise ValueError("--count must be non-negative")
    if args.retained_refresh_seconds < 0:
        raise ValueError("--retained-refresh-seconds must be non-negative")
    if args.config_projection_timeout_seconds < 0:
        raise ValueError("--config-projection-timeout-seconds must be non-negative")
    config_delivery = "none" if args.no_config else args.config_delivery

    bundle = load_bundle(args.bundle_config)
    selected_source = bundle.source(args.source_id)

    return DemoSettings(
        broker=parse_broker(args.broker),
        kafka=KafkaConfig(
            bootstrap_servers=args.kafka_bootstrap_servers,
            client_id=args.kafka_client_id,
        ),
        idp_config_registry=ConfigRegistryConfig(
            base_url=args.config_registry_url.rstrip("/")
        ),
        username=args.username,
        password=args.password,
        client_id=args.client_id,
        scope=TopicScope(
            topic_root=args.topic_root,
            asset_id=bundle.asset_id,
            agent_id=bundle.agent_id,
        ),
        bundle=bundle,
        telemetry_source_id=selected_source.source_id,
        interval_seconds=args.interval_seconds,
        count=args.count,
        temperature=WaveConfig(
            base=args.temperature_base,
            amplitude=args.temperature_amplitude,
            period=args.temperature_period,
        ),
        config_delivery=config_delivery,
        publish_config=config_delivery == "mqtt",
        publish_status=not args.no_status,
        retained_refresh_seconds=args.retained_refresh_seconds,
    )


def main() -> int:
    args = parse_args()
    try:
        settings = settings_from_args(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    if settings.config_delivery == "kafka":
        kafka_publisher = connect_kafka_publisher(config=settings.kafka)
        try:
            records = config_delivery_records(settings)
            for record in records:
                kafka_publisher.publish(record)
            print(
                "PUBLISHED_CONFIG_DELIVERY "
                f"records={len(records)} "
                f"bootstrap_servers={settings.kafka.bootstrap_servers} "
                f"agent_id={settings.bundle.agent_id}"
            )
        finally:
            kafka_publisher.close()
        wait_for_retained_config_projection(
            settings,
            timeout_seconds=args.config_projection_timeout_seconds,
        )
        settings = replace(settings, publish_config=False)
    elif settings.config_delivery == "api":
        publish_bundle_via_idp_config_registry(
            config=settings.idp_config_registry,
            bundle=settings.bundle,
        )
        wait_for_retained_config_projection(
            settings,
            timeout_seconds=args.config_projection_timeout_seconds,
        )
        settings = replace(settings, publish_config=False)

    publisher = connect_publisher(settings=settings)
    print(
        "CONNECTED "
        f"broker={settings.broker.host}:{settings.broker.port} "
        f"asset_id={settings.bundle.asset_id} "
        f"agent_id={settings.bundle.agent_id} "
        f"source_id={settings.telemetry_source_id}"
    )
    try:
        return run_demo(
            settings,
            publisher=publisher,
            runtime=SystemRuntime(),
        )
    finally:
        publisher.close()
        print("DISCONNECTED")
