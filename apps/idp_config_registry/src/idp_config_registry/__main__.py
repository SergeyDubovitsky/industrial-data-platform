from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

import uvicorn

from idp_config_registry.application.ports.config_delivery import ConfigRecordPublisher
from idp_config_registry.application.use_cases.config_event_publisher import (
    PublishConfigOutboxBatch,
    PublishConfigOutboxBatchCommand,
    PublishConfigOutboxBatchResult,
)
from idp_config_registry.infrastructure.kafka.config_delivery import (
    ConfluentKafkaConfigRecordPublisher,
)
from idp_config_registry.infrastructure.postgres.unit_of_work import (
    PostgresUnitOfWorkFactory,
)
from idp_config_registry.settings import ConfigRegistrySettings


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    command = args.command or "serve"
    if command == "serve":
        _serve()
        return
    if command == "publish-config-outbox-once":
        asyncio.run(_publish_config_outbox_once(args))
        return
    if command == "publish-config-outbox-worker":
        asyncio.run(_publish_config_outbox_worker(args))
        return
    parser.error(f"Unknown command {command!r}")


def _serve() -> None:
    settings = ConfigRegistrySettings.from_env()
    uvicorn.run(
        "idp_config_registry.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="idp-config-registry")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("serve", help="Run the Config Registry HTTP API")
    publish_parser = subparsers.add_parser(
        "publish-config-outbox-once",
        help="Publish one batch of pending config outbox records to Kafka",
    )
    publish_parser.add_argument("--limit", type=int)
    publish_parser.add_argument("--lease-seconds", type=int)
    publish_parser.add_argument("--retry-delay-seconds", type=int)
    publish_parser.add_argument("--max-attempts", type=int)
    worker_parser = subparsers.add_parser(
        "publish-config-outbox-worker",
        help="Continuously publish pending config outbox records to Kafka",
    )
    worker_parser.add_argument("--limit", type=int)
    worker_parser.add_argument("--lease-seconds", type=int)
    worker_parser.add_argument("--retry-delay-seconds", type=int)
    worker_parser.add_argument("--max-attempts", type=int)
    worker_parser.add_argument("--poll-interval-seconds", type=float)
    return parser


async def _publish_config_outbox_once(args: argparse.Namespace) -> None:
    result = await _publish_config_outbox_batch(args)

    print(
        "Config outbox publish batch: "
        f"reserved={result.reserved} "
        f"published={result.published} "
        f"retried={result.retried} "
        f"dead_lettered={result.dead_lettered}"
    )


async def _publish_config_outbox_worker(args: argparse.Namespace) -> None:
    settings = ConfigRegistrySettings.from_env()
    if settings.database_url is None:
        raise SystemExit("CONFIG_REGISTRY_DATABASE_URL must be set")
    poll_interval_seconds = (
        args.poll_interval_seconds or settings.outbox_poll_interval_seconds
    )
    unit_of_work_factory = PostgresUnitOfWorkFactory.from_url(settings.database_url)
    publisher = ConfluentKafkaConfigRecordPublisher.from_bootstrap_servers(
        settings.kafka_bootstrap_servers,
        client_id=settings.kafka_client_id,
    )
    print(
        "Config outbox worker started: "
        f"poll_interval_seconds={poll_interval_seconds} "
        f"batch_limit={args.limit or settings.outbox_batch_limit}"
    )
    try:
        while True:
            result = await _publish_config_outbox_batch(
                args,
                settings=settings,
                unit_of_work_factory=unit_of_work_factory,
                publisher=publisher,
            )
            if (
                result.reserved
                or result.published
                or result.retried
                or result.dead_lettered
            ):
                print(
                    "Config outbox publish batch: "
                    f"reserved={result.reserved} "
                    f"published={result.published} "
                    f"retried={result.retried} "
                    f"dead_lettered={result.dead_lettered}"
                )
            await asyncio.sleep(poll_interval_seconds)
    finally:
        await unit_of_work_factory.dispose()


async def _publish_config_outbox_batch(
    args: argparse.Namespace,
    *,
    settings: ConfigRegistrySettings | None = None,
    unit_of_work_factory: PostgresUnitOfWorkFactory | None = None,
    publisher: ConfigRecordPublisher | None = None,
) -> PublishConfigOutboxBatchResult:
    settings = settings or ConfigRegistrySettings.from_env()
    if settings.database_url is None:
        raise SystemExit("CONFIG_REGISTRY_DATABASE_URL must be set")

    owns_unit_of_work_factory = unit_of_work_factory is None
    unit_of_work_factory = unit_of_work_factory or PostgresUnitOfWorkFactory.from_url(
        settings.database_url
    )
    publisher = publisher or ConfluentKafkaConfigRecordPublisher.from_bootstrap_servers(
        settings.kafka_bootstrap_servers,
        client_id=settings.kafka_client_id,
    )
    try:
        result = await PublishConfigOutboxBatch(
            unit_of_work_factory,
            publisher,
        ).execute(
            PublishConfigOutboxBatchCommand(
                now=datetime.now(tz=UTC),
                limit=args.limit or settings.outbox_batch_limit,
                lease_duration=timedelta(
                    seconds=args.lease_seconds or settings.outbox_lease_seconds
                ),
                retry_delay=timedelta(
                    seconds=(
                        args.retry_delay_seconds
                        or settings.outbox_retry_delay_seconds
                    )
                ),
                max_attempts=args.max_attempts or settings.outbox_max_attempts,
            )
        )
    finally:
        if owns_unit_of_work_factory:
            await unit_of_work_factory.dispose()

    return result


if __name__ == "__main__":
    main()
