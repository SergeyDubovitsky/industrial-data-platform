from __future__ import annotations

import pytest

from idp_synthetic_config.generator import GeneratorOptions, generate_synthetic_config
from idp_synthetic_config.reset import DestructiveResetRefused, ResetPolicy


def test_local_reset_policy_is_enabled_by_default_for_local_targets() -> None:
    model = generate_synthetic_config(GeneratorOptions(seed=1))

    summary = ResetPolicy().evaluate(
        model,
        config_registry_url="http://localhost:8000",
    )

    assert summary.enabled is True
    assert summary.target_kind == "local"
    assert {target.name for target in summary.targets} == {
        "config_registry",
        "clickhouse",
        "mqtt_retained_config",
    }
    assert all(target.status in {"planned", "skipped"} for target in summary.targets)


def test_reset_policy_can_be_disabled_for_seed_without_reset() -> None:
    model = generate_synthetic_config(GeneratorOptions(seed=1))

    summary = ResetPolicy(enabled=False).evaluate(
        model,
        config_registry_url="https://config.example.com",
    )

    assert summary.enabled is False
    assert summary.target_kind == "disabled"
    assert summary.targets == ()


def test_non_local_reset_requires_explicit_destructive_opt_in() -> None:
    model = generate_synthetic_config(GeneratorOptions(seed=1))

    with pytest.raises(DestructiveResetRefused, match="non-local"):
        ResetPolicy().evaluate(
            model,
            config_registry_url="https://config.example.com",
        )


def test_unlisted_single_label_endpoint_is_not_treated_as_local() -> None:
    model = generate_synthetic_config(GeneratorOptions(seed=1))

    with pytest.raises(DestructiveResetRefused, match="non-local"):
        ResetPolicy().evaluate(
            model,
            config_registry_url="http://staging:8000",
        )


def test_non_local_reset_with_opt_in_records_warning() -> None:
    model = generate_synthetic_config(GeneratorOptions(seed=1))

    summary = ResetPolicy(allow_destructive_reset=True).evaluate(
        model,
        config_registry_url="https://config.example.com",
    )

    assert summary.target_kind == "non-local"
    assert summary.warning is not None
    assert "--allow-destructive-reset" in summary.warning


def test_configured_unimplemented_reset_targets_are_reported_as_unsupported() -> None:
    model = generate_synthetic_config(GeneratorOptions(seed=1))

    summary = ResetPolicy(
        clickhouse_url="http://localhost:8123",
        mqtt_broker_url="mqtt://localhost:1883",
    ).evaluate(
        model,
        config_registry_url="http://localhost:8000",
    )

    statuses = {target.name: target.status for target in summary.targets}
    assert statuses["config_registry"] == "planned"
    assert statuses["clickhouse"] == "unsupported"
    assert statuses["mqtt_retained_config"] == "unsupported"
