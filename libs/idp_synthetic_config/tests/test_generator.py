from __future__ import annotations

import json
import re
from urllib.parse import quote

import pytest

from idp_synthetic_config.generator import GeneratorOptions, generate_synthetic_config

MQTT_PATH_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
KNX_GROUP_ADDRESS = re.compile(r"^\d{1,2}/\d/\d{1,3}$")


def test_default_generation_is_deterministic_and_safe_for_local_smoke() -> None:
    first = generate_synthetic_config(GeneratorOptions(seed=42))
    second = generate_synthetic_config(GeneratorOptions(seed=42))

    assert first.to_plan_dict() == second.to_plan_dict()
    assert len(first.devices) == 3
    assert sum(len(source.points) for source in first.sources) == 30
    assert first.tenant.name.startswith("ТЦ ")
    assert first.asset.name.startswith("ТЦ ")
    assert "lorem" not in json.dumps(first.to_plan_dict(), ensure_ascii=False).lower()


def test_generated_points_have_stable_registry_and_knx_identifiers() -> None:
    model = generate_synthetic_config(
        GeneratorOptions(
            seed=7,
            devices=4,
            tags_per_device=8,
            tenant_id="tenant-synth",
            asset_id="mall-synth-01",
            agent_id="edge-synth-01",
            source_id="knx_synthetic",
        )
    )

    assert MQTT_PATH_ID.fullmatch(model.asset.asset_id)
    assert MQTT_PATH_ID.fullmatch(model.agent.agent_id)
    assert MQTT_PATH_ID.fullmatch(model.sources[0].source_id)

    seen_refs: set[str] = set()
    for source in model.sources:
        for point in source.points:
            assert point.point_ref not in seen_refs
            seen_refs.add(point.point_ref)
            assert KNX_GROUP_ADDRESS.fullmatch(point.point_ref)
            assert point.point_key == quote(point.point_ref, safe="")
            assert point.point_id == (
                f"{model.tenant.tenant_id}|{model.asset.asset_id}|"
                f"{source.source_id}|{point.point_key}"
            )


def test_generated_point_names_are_unique_at_upper_local_load_profile() -> None:
    model = generate_synthetic_config(
        GeneratorOptions(seed=7, devices=100, tags_per_device=100)
    )
    names = [point.name for source in model.sources for point in source.points]

    assert len(names) == 10_000
    assert len(set(names)) == len(names)


def test_generated_points_cover_value_and_signal_variants_with_operator_settings() -> None:
    model = generate_synthetic_config(
        GeneratorOptions(seed=13, devices=3, tags_per_device=10)
    )
    points = [point for source in model.sources for point in source.points]

    assert {point.value_type for point in points} == {"boolean", "number", "string"}
    assert {point.signal_type for point in points} == {
        "command",
        "feedback",
        "sensor",
        "status",
    }

    for point in points:
        assert isinstance(point.acquisition["read_on_start"], bool)
        assert point.acquisition["periodic_interval_seconds"] > 0
        if point.value_type == "number":
            assert point.publish["change_threshold"] is not None
        else:
            assert point.publish["change_threshold"] is None


def test_generated_names_and_descriptions_are_russian_and_domain_specific() -> None:
    model = generate_synthetic_config(GeneratorOptions(seed=23))
    plan_text = json.dumps(model.to_plan_dict(), ensure_ascii=False)

    assert any("а" <= char.lower() <= "я" for char in plan_text)
    assert "торгов" in plan_text.lower()
    assert "этаж" in plan_text.lower()
    assert "read_on_start" in plan_text

    point = model.sources[0].points[0]
    assert point.name
    assert point.description is not None
    assert "Периодический опрос" in point.description
    assert "порог публикации" in point.description
    assert point.tags["generated_by"] == "idp_synthetic_config"


def test_generation_rejects_scale_above_local_load_profile() -> None:
    with pytest.raises(ValueError, match="devices"):
        generate_synthetic_config(GeneratorOptions(devices=101))

    with pytest.raises(ValueError, match="tags_per_device"):
        generate_synthetic_config(GeneratorOptions(tags_per_device=101))
