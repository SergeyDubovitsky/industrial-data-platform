from __future__ import annotations

import random
import re
from dataclasses import dataclass
from urllib.parse import quote

from idp_synthetic_config.models import (
    JsonObject,
    SyntheticAgent,
    SyntheticAsset,
    SyntheticDevice,
    SyntheticModel,
    SyntheticPoint,
    SyntheticSource,
    SyntheticTenant,
    ValueProfile,
)

MAX_LOCAL_LOAD_DEVICES = 100
MAX_LOCAL_LOAD_TAGS_PER_DEVICE = 100
MQTT_PATH_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")

MALL_NAMES = (
    "ТЦ Северный Пассаж",
    "ТЦ Городские Галереи",
    "ТЦ Атриум Парк",
    "ТЦ Южный Молл",
)
FLOORS = ("этаж -1", "этаж 1", "этаж 2", "этаж 3", "этаж 4")
ZONES = (
    "Главный вход",
    "Фудкорт",
    "Галерея бутиков",
    "Кинотеатр",
    "Парковка",
    "Атриум",
    "Сервисный коридор",
    "Техническая зона",
)
TENANT_SPACES = (
    "витрина электроники",
    "магазин одежды",
    "кофейня",
    "детская зона",
    "супермаркет",
    "аптека",
    "служба эксплуатации",
)
SUBSYSTEMS = (
    "HVAC",
    "Освещение",
    "Эскалаторы",
    "Лифты",
    "Насосы",
    "Энергомониторинг",
    "Парковка",
    "Качество воздуха",
    "Пожарная сигнализация",
    "Охранная сигнализация",
)


@dataclass(frozen=True)
class GeneratorOptions:
    devices: int = 3
    tags_per_device: int = 10
    tenant_id: str = "synthetic-tenant"
    asset_id: str = "mall-synthetic-01"
    agent_id: str = "edge-synthetic-01"
    source_id: str = "knx_synthetic"
    seed: int = 20260510
    profile: str = "mall"


@dataclass(frozen=True)
class PointTemplate:
    label: str
    purpose: str
    value_type: str
    value_model: str
    signal_type: str
    unit: str | None
    periodic_interval_seconds: int
    change_threshold: float | None
    read_on_start: bool
    profile_parameters: JsonObject


POINT_TEMPLATES = (
    PointTemplate(
        label="Температура воздуха",
        purpose="Контроль температуры воздуха",
        value_type="number",
        value_model="knx.dpt.9.001",
        signal_type="sensor",
        unit="C",
        periodic_interval_seconds=60,
        change_threshold=0.5,
        read_on_start=True,
        profile_parameters={"base": 22.0, "amplitude": 3.0, "period_seconds": 900},
    ),
    PointTemplate(
        label="Влажность",
        purpose="Контроль относительной влажности",
        value_type="number",
        value_model="knx.dpt.9.007",
        signal_type="sensor",
        unit="%",
        periodic_interval_seconds=120,
        change_threshold=2.0,
        read_on_start=True,
        profile_parameters={"base": 45.0, "amplitude": 8.0, "period_seconds": 1200},
    ),
    PointTemplate(
        label="Состояние освещения",
        purpose="Обратная связь группы освещения",
        value_type="boolean",
        value_model="knx.dpt.1.001",
        signal_type="feedback",
        unit=None,
        periodic_interval_seconds=300,
        change_threshold=None,
        read_on_start=True,
        profile_parameters={"true_ratio": 0.7},
    ),
    PointTemplate(
        label="Команда освещения",
        purpose="Командная точка управления освещением",
        value_type="boolean",
        value_model="knx.dpt.1.001",
        signal_type="command",
        unit=None,
        periodic_interval_seconds=300,
        change_threshold=None,
        read_on_start=False,
        profile_parameters={"command_values": ["on", "off"]},
    ),
    PointTemplate(
        label="Энергопотребление",
        purpose="Счетчик потребления электроэнергии",
        value_type="number",
        value_model="knx.dpt.13.010",
        signal_type="sensor",
        unit="kWh",
        periodic_interval_seconds=300,
        change_threshold=1.0,
        read_on_start=True,
        profile_parameters={"base": 120.0, "amplitude": 30.0, "period_seconds": 1800},
    ),
    PointTemplate(
        label="Режим работы",
        purpose="Текстовый режим работы оборудования",
        value_type="string",
        value_model="knx.dpt.16.001",
        signal_type="status",
        unit=None,
        periodic_interval_seconds=300,
        change_threshold=None,
        read_on_start=True,
        profile_parameters={"values": ["авто", "ручной", "экономичный"]},
    ),
    PointTemplate(
        label="Аварийный сигнал",
        purpose="Дискретный сигнал аварии",
        value_type="boolean",
        value_model="knx.dpt.1.005",
        signal_type="status",
        unit=None,
        periodic_interval_seconds=60,
        change_threshold=None,
        read_on_start=True,
        profile_parameters={"true_ratio": 0.02},
    ),
    PointTemplate(
        label="Положение привода",
        purpose="Обратная связь положения клапана или заслонки",
        value_type="number",
        value_model="knx.dpt.5.001",
        signal_type="feedback",
        unit="%",
        periodic_interval_seconds=60,
        change_threshold=1.0,
        read_on_start=True,
        profile_parameters={"base": 50.0, "amplitude": 35.0, "period_seconds": 700},
    ),
    PointTemplate(
        label="Состояние связи",
        purpose="Текстовое состояние связи с оборудованием",
        value_type="string",
        value_model="knx.dpt.16.001",
        signal_type="status",
        unit=None,
        periodic_interval_seconds=120,
        change_threshold=None,
        read_on_start=True,
        profile_parameters={"values": ["норма", "потеря связи", "обслуживание"]},
    ),
    PointTemplate(
        label="CO2",
        purpose="Контроль качества воздуха по CO2",
        value_type="number",
        value_model="knx.dpt.9.008",
        signal_type="sensor",
        unit="ppm",
        periodic_interval_seconds=60,
        change_threshold=50.0,
        read_on_start=True,
        profile_parameters={"base": 650.0, "amplitude": 250.0, "period_seconds": 1000},
    ),
)


def generate_synthetic_config(options: GeneratorOptions | None = None) -> SyntheticModel:
    resolved = options or GeneratorOptions()
    _validate_options(resolved)
    randomizer = random.Random(resolved.seed)

    mall_name = MALL_NAMES[randomizer.randrange(len(MALL_NAMES))]
    tenant = SyntheticTenant(
        tenant_id=resolved.tenant_id,
        name=f"{mall_name} - synthetic tenant",
    )
    asset = SyntheticAsset(
        asset_id=resolved.asset_id,
        name=mall_name,
        description=(
            "Синтетический цифровой двойник большого торгового центра: зоны, "
            "этажи, арендаторы и инженерные системы для local/dev стенда."
        ),
    )
    agent = SyntheticAgent(
        agent_id=resolved.agent_id,
        name="Edge агент синтетического ТЦ",
        bootstrap_hint_json={
            "profile": "local-synthetic",
            "source": "idp_synthetic_config",
        },
    )

    devices = _devices(resolved, randomizer=randomizer)
    points: list[SyntheticPoint] = []
    value_profiles: list[ValueProfile] = []
    for device_index, device in enumerate(devices):
        for tag_index in range(resolved.tags_per_device):
            ordinal = device_index * resolved.tags_per_device + tag_index
            template = POINT_TEMPLATES[ordinal % len(POINT_TEMPLATES)]
            point = _point(
                tenant_id=tenant.tenant_id,
                asset_id=asset.asset_id,
                source_id=resolved.source_id,
                device=device,
                template=template,
                ordinal=ordinal,
                tag_index=tag_index,
            )
            points.append(point)
            value_profiles.append(_value_profile(point, template))

    source = SyntheticSource(
        source_id=resolved.source_id,
        source_type="knx",
        enabled=True,
        name="KNX линия синтетического ТЦ",
        description=(
            f"Синтетический KNX source для {asset.name}: "
            f"{resolved.devices} устройств, {len(points)} точек."
        ),
        connection_json={
            "gateway_ip": "127.0.0.1",
            "gateway_port": 3671,
            "mode": "synthetic",
        },
        acquisition_defaults_json={
            "listen": True,
            "read_on_start": False,
            "periodic_interval_seconds": 60,
        },
        publish_defaults_json={
            "enabled": True,
            "change_threshold": None,
        },
        points=tuple(points),
    )
    return SyntheticModel(
        tenant=tenant,
        asset=asset,
        agent=agent,
        sources=(source,),
        devices=devices,
        value_profiles=tuple(value_profiles),
        seed=resolved.seed,
    )


def point_key_from_ref(point_ref: str) -> str:
    return quote(point_ref, safe="")


def _validate_options(options: GeneratorOptions) -> None:
    if options.profile != "mall":
        raise ValueError("profile must be 'mall'")
    if not 1 <= options.devices <= MAX_LOCAL_LOAD_DEVICES:
        raise ValueError(
            f"devices must be between 1 and {MAX_LOCAL_LOAD_DEVICES}"
        )
    if not 1 <= options.tags_per_device <= MAX_LOCAL_LOAD_TAGS_PER_DEVICE:
        raise ValueError(
            "tags_per_device must be between 1 and "
            f"{MAX_LOCAL_LOAD_TAGS_PER_DEVICE}"
        )
    for field_name, value in (
        ("asset_id", options.asset_id),
        ("agent_id", options.agent_id),
        ("source_id", options.source_id),
    ):
        if MQTT_PATH_ID.fullmatch(value) is None:
            raise ValueError(f"{field_name} must match mqtt_path_id")
    if not options.tenant_id.strip():
        raise ValueError("tenant_id must be non-empty")


def _devices(
    options: GeneratorOptions,
    *,
    randomizer: random.Random,
) -> tuple[SyntheticDevice, ...]:
    devices: list[SyntheticDevice] = []
    for index in range(options.devices):
        floor = FLOORS[(index + randomizer.randrange(len(FLOORS))) % len(FLOORS)]
        zone = ZONES[(index * 3 + randomizer.randrange(len(ZONES))) % len(ZONES)]
        subsystem = SUBSYSTEMS[index % len(SUBSYSTEMS)]
        tenant_space = TENANT_SPACES[
            (index * 2 + randomizer.randrange(len(TENANT_SPACES)))
            % len(TENANT_SPACES)
        ]
        device_id = f"device-{index + 1:03d}"
        devices.append(
            SyntheticDevice(
                device_id=device_id,
                name=f"{subsystem}: {zone}, {floor}",
                floor=floor,
                zone=zone,
                subsystem=subsystem,
                tenant_space=tenant_space,
            )
        )
    return tuple(devices)


def _point(
    *,
    tenant_id: str,
    asset_id: str,
    source_id: str,
    device: SyntheticDevice,
    template: PointTemplate,
    ordinal: int,
    tag_index: int,
) -> SyntheticPoint:
    point_ref = _knx_group_address(ordinal)
    point_key = point_key_from_ref(point_ref)
    point_id = f"{tenant_id}|{asset_id}|{source_id}|{point_key}"
    read_on_start = template.read_on_start
    acquisition = {
        "listen": True,
        "read_on_start": read_on_start,
        "periodic_interval_seconds": template.periodic_interval_seconds,
    }
    publish = {
        "enabled": template.signal_type != "command",
        "change_threshold": (
            template.change_threshold if template.value_type == "number" else None
        ),
    }
    threshold_text = (
        str(publish["change_threshold"])
        if publish["change_threshold"] is not None
        else "null"
    )
    name = (
        f"{template.label} {tag_index + 1:03d}: "
        f"{device.zone}, {device.floor}, {device.device_id}"
    )
    description = (
        f"{template.purpose} в зоне {device.zone}, {device.floor}, "
        f"{device.tenant_space}. Периодический опрос: "
        f"{template.periodic_interval_seconds} c, порог публикации: "
        f"{threshold_text}, read_on_start: {str(read_on_start).lower()}, "
        f"signal_type: {template.signal_type}, value_model: {template.value_model}."
    )
    return SyntheticPoint(
        point_id=point_id,
        point_key=point_key,
        point_ref=point_ref,
        name=name,
        description=description,
        value_type=template.value_type,
        value_model=template.value_model,
        signal_type=template.signal_type,
        unit=template.unit,
        acquisition=acquisition,
        publish=publish,
        tags={
            "generated_by": "idp_synthetic_config",
            "profile": "local-synthetic-mall",
            "floor": device.floor,
            "zone": device.zone,
            "subsystem": device.subsystem,
            "tenant_space": device.tenant_space,
            "device_id": device.device_id,
            "point_index": str(tag_index),
            "signal_type": template.signal_type,
            "value_model": template.value_model,
        },
    )


def _knx_group_address(ordinal: int) -> str:
    main = 1 + ordinal // (8 * 255)
    middle = (ordinal // 255) % 8
    sub = 1 + ordinal % 255
    if main > 15:
        raise ValueError("too many points for KNX three-level group address space")
    return f"{main}/{middle}/{sub}"


def _value_profile(point: SyntheticPoint, template: PointTemplate) -> ValueProfile:
    return ValueProfile(
        profile_id=f"value-profile:{point.point_key}",
        point_id=point.point_id,
        value_type=point.value_type,
        signal_type=point.signal_type,
        parameters={
            **template.profile_parameters,
            "value_model": point.value_model,
            "unit": point.unit,
        },
    )
