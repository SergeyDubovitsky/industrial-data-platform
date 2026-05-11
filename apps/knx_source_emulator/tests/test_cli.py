from __future__ import annotations

import io
import json
from typing import Any

from idp_synthetic_config.config_registry_seeder import SeedSummary
from idp_synthetic_config.reset import ResetSummary
from knx_source_emulator import cli


def test_plan_dry_run_prints_russian_names_and_generated_settings() -> None:
    stdout = io.StringIO()

    exit_code = cli.main(
        [
            "plan",
            "--dry-run",
            "--format",
            "json",
            "--seed",
            "5",
            "--devices",
            "1",
            "--tags-per-device",
            "2",
        ],
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    first_point = payload["sources"][0]["points"][0]
    assert exit_code == 0
    assert payload["dry_run"] is True
    assert any("а" <= char.lower() <= "я" for char in first_point["name"])
    assert first_point["point_ref"] == "1/0/1"
    assert first_point["periodic_interval_seconds"] == 60
    assert first_point["change_threshold"] == 0.5
    assert first_point["read_on_start"] is True
    assert first_point["signal_type"] == "sensor"
    assert first_point["value_model"] == "knx.dpt.9.001"


def test_seed_config_uses_synthetic_config_seeder(monkeypatch) -> None:
    stdout = io.StringIO()
    captured: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, base_url: str, *, timeout_seconds: float) -> None:
            captured["base_url"] = base_url
            captured["timeout_seconds"] = timeout_seconds

    class FakeSeeder:
        def __init__(self, client: FakeClient, *, reset_policy) -> None:
            captured["client"] = client
            captured["reset_policy"] = reset_policy

        def seed(self, model, **kwargs):
            captured["model"] = model
            captured["seed_kwargs"] = kwargs
            return SeedSummary(
                config_revision="synthetic-test",
                issued_at="2026-05-10T12:00:00Z",
                source_config_revisions={"knx_synthetic": "synthetic-test-knx_synthetic"},
                reset=ResetSummary(
                    enabled=False,
                    target_kind="disabled",
                    warning=None,
                    targets=(),
                ),
                entries=(),
                render_response={"status": "ok"},
            )

    monkeypatch.setattr(cli, "ConfigRegistryHttpClient", FakeClient)
    monkeypatch.setattr(cli, "ConfigRegistrySeeder", FakeSeeder)

    exit_code = cli.main(
        [
            "seed-config",
            "--format",
            "json",
            "--devices",
            "1",
            "--tags-per-device",
            "1",
            "--config-registry-url",
            "http://registry.local",
            "--timeout-seconds",
            "12.5",
            "--no-reset",
        ],
        stdout=stdout,
    )

    payload = json.loads(stdout.getvalue())
    assert exit_code == 0
    assert payload["ok"] is True
    assert captured["base_url"] == "http://registry.local"
    assert captured["timeout_seconds"] == 12.5
    assert captured["model"].sources[0].source_type == "knx"
    assert captured["model"].sources[0].points[0].point_ref == "1/0/1"
    assert captured["seed_kwargs"]["config_registry_url"] == "http://registry.local"
    assert captured["reset_policy"].enabled is False
