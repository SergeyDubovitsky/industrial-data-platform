from __future__ import annotations

from idp_synthetic_config.generator import GeneratorOptions, generate_synthetic_config
from knx_source_emulator.plan import (
    build_emulator_plan,
    build_emulator_plan_from_source_config,
)


def test_emulator_plan_uses_synthetic_config_points_and_value_profiles() -> None:
    model = generate_synthetic_config(
        GeneratorOptions(devices=1, tags_per_device=6, seed=42)
    )

    plan = build_emulator_plan(
        model,
        host="127.0.0.1",
        port=0,
        interval_seconds=0.05,
    )

    assert plan.host == "127.0.0.1"
    assert plan.source_id == "knx_synthetic"
    assert plan.point_count == 6
    assert plan.stream_points
    assert plan.command_points
    assert {point.signal_type for point in plan.stream_points} == {
        "feedback",
        "sensor",
        "status",
    }

    temperature = next(point for point in plan.points if point.value_type == "number")
    assert "Температура" in temperature.name
    assert temperature.description is not None
    assert "Периодический опрос" in temperature.description
    assert temperature.periodic_interval_seconds == 60
    assert temperature.change_threshold == 0.5
    assert temperature.read_on_start is True
    assert temperature.profile.parameters["base"] == 22.0


def test_plan_dry_run_dict_contains_operator_settings_and_russian_text() -> None:
    model = generate_synthetic_config(
        GeneratorOptions(devices=1, tags_per_device=4, seed=7)
    )

    plan = build_emulator_plan(model, host="127.0.0.1", port=12345)
    payload = plan.to_dict()

    first_point = payload["points"][0]
    assert payload["stats"]["devices"] == 1
    assert payload["stats"]["points"] == 4
    assert "name" in first_point
    assert "description" in first_point
    assert "periodic_interval_seconds" in first_point
    assert "change_threshold" in first_point
    assert "read_on_start" in first_point
    assert "signal_type" in first_point
    assert "value_model" in first_point


def test_plan_can_be_built_from_rendered_source_config_and_value_profiles() -> None:
    model = generate_synthetic_config(
        GeneratorOptions(devices=1, tags_per_device=4, seed=11)
    )
    source_config = model.source_config_payloads(
        config_revision="rev-test",
        source_config_revisions={"knx_synthetic": "rev-test-knx_synthetic"},
    )[0]
    source_config["connection"] = {
        **source_config["connection"],
        "host": "127.0.0.1",
        "port": 38123,
    }

    plan = build_emulator_plan_from_source_config(
        source_config,
        value_profiles=model.value_profiles,
        devices=len(model.devices),
        emission_interval_seconds=0.01,
    )

    first_point = plan.points[0]
    assert plan.host == "127.0.0.1"
    assert plan.port == 38123
    assert first_point.point_ref == source_config["points"][0]["point_ref"]
    assert first_point.periodic_interval_seconds == 60
    assert first_point.change_threshold == 0.5
    assert first_point.profile.parameters["base"] == 22.0


def test_plan_accepts_nullable_point_description_from_contract_payload() -> None:
    model = generate_synthetic_config(
        GeneratorOptions(devices=1, tags_per_device=1, seed=11)
    )
    source_config = model.source_config_payloads(
        config_revision="rev-test",
        source_config_revisions={"knx_synthetic": "rev-test-knx_synthetic"},
    )[0]
    source_config["points"][0]["description"] = None

    plan = build_emulator_plan_from_source_config(
        source_config,
        value_profiles=model.value_profiles,
    )

    assert plan.points[0].description is None
