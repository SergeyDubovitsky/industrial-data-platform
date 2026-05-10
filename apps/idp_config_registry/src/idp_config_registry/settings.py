from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ConfigRegistrySettings:
    host: str = "127.0.0.1"
    port: int = 8000
    internal_mode: bool = True
    database_url: str | None = None
    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_client_id: str = "idp-config-registry"
    outbox_batch_limit: int = 100
    outbox_lease_seconds: int = 30
    outbox_retry_delay_seconds: int = 30
    outbox_max_attempts: int = 5
    outbox_poll_interval_seconds: float = 2.0

    @classmethod
    def from_env(cls) -> ConfigRegistrySettings:
        return cls(
            host=os.getenv("CONFIG_REGISTRY_HOST", "127.0.0.1"),
            port=int(os.getenv("CONFIG_REGISTRY_PORT", "8000")),
            internal_mode=os.getenv("CONFIG_REGISTRY_INTERNAL_MODE", "true").lower()
            in {"1", "true", "yes"},
            database_url=os.getenv("CONFIG_REGISTRY_DATABASE_URL"),
            kafka_bootstrap_servers=os.getenv(
                "KAFKA_BOOTSTRAP_SERVERS",
                "localhost:19092",
            ),
            kafka_client_id=os.getenv(
                "CONFIG_REGISTRY_KAFKA_CLIENT_ID",
                "idp-config-registry",
            ),
            outbox_batch_limit=int(
                os.getenv("CONFIG_REGISTRY_OUTBOX_BATCH_LIMIT", "100")
            ),
            outbox_lease_seconds=int(
                os.getenv("CONFIG_REGISTRY_OUTBOX_LEASE_SECONDS", "30")
            ),
            outbox_retry_delay_seconds=int(
                os.getenv("CONFIG_REGISTRY_OUTBOX_RETRY_DELAY_SECONDS", "30")
            ),
            outbox_max_attempts=int(
                os.getenv("CONFIG_REGISTRY_OUTBOX_MAX_ATTEMPTS", "5")
            ),
            outbox_poll_interval_seconds=float(
                os.getenv("CONFIG_REGISTRY_OUTBOX_POLL_INTERVAL_SECONDS", "2.0")
            ),
        )
