from __future__ import annotations

from idp_config_registry.settings import ConfigRegistrySettings


def test_config_registry_settings_reads_kafka_and_outbox_env(monkeypatch) -> None:
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
    monkeypatch.setenv("CONFIG_REGISTRY_KAFKA_CLIENT_ID", "idp-config-registry-it")
    monkeypatch.setenv("CONFIG_REGISTRY_OUTBOX_BATCH_LIMIT", "25")
    monkeypatch.setenv("CONFIG_REGISTRY_OUTBOX_LEASE_SECONDS", "45")
    monkeypatch.setenv("CONFIG_REGISTRY_OUTBOX_RETRY_DELAY_SECONDS", "60")
    monkeypatch.setenv("CONFIG_REGISTRY_OUTBOX_MAX_ATTEMPTS", "7")
    monkeypatch.setenv("CONFIG_REGISTRY_OUTBOX_POLL_INTERVAL_SECONDS", "2.5")

    settings = ConfigRegistrySettings.from_env()

    assert settings.kafka_bootstrap_servers == "127.0.0.1:19092"
    assert settings.kafka_client_id == "idp-config-registry-it"
    assert settings.outbox_batch_limit == 25
    assert settings.outbox_lease_seconds == 45
    assert settings.outbox_retry_delay_seconds == 60
    assert settings.outbox_max_attempts == 7
    assert settings.outbox_poll_interval_seconds == 2.5
