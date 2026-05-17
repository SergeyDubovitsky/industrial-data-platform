from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from idp_config_registry.application.errors import (
    DuplicatePointError,
    PointNotFoundError,
    SourceNotFoundError,
)
from idp_config_registry.application.ports.unit_of_work import UnitOfWork
from idp_config_registry.domain.entities import Point, utc_now
from idp_config_registry.domain.value_objects import SignalType, ValueType


@dataclass(frozen=True)
class CreatePointCommand:
    tenant_code: str
    asset_code: str
    agent_code: str
    source_code: str
    point_code: str
    point_key: str
    point_ref: str
    name: str
    value_type: ValueType
    value_model: str
    signal_type: SignalType
    description: str | None = None
    unit: str | None = None
    enabled: bool = True
    acquisition_json: dict[str, Any] = field(default_factory=dict)
    publish_json: dict[str, Any] = field(default_factory=dict)
    tags_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdatePointCommand:
    tenant_code: str
    point_code: str
    point_key: str
    point_ref: str
    name: str
    value_type: ValueType
    value_model: str
    signal_type: SignalType
    description: str | None = None
    unit: str | None = None
    enabled: bool = True
    acquisition_json: dict[str, Any] = field(default_factory=dict)
    publish_json: dict[str, Any] = field(default_factory=dict)
    tags_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeletePointCommand:
    tenant_code: str
    point_code: str
    asset_code: str | None = None
    agent_code: str | None = None
    source_code: str | None = None


class CreatePoint:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreatePointCommand) -> Point:
        point = Point(
            tenant_code=command.tenant_code,
            asset_code=command.asset_code,
            agent_code=command.agent_code,
            source_code=command.source_code,
            point_code=command.point_code,
            point_key=command.point_key,
            point_ref=command.point_ref,
            name=command.name,
            value_type=command.value_type,
            value_model=command.value_model,
            signal_type=command.signal_type,
            description=command.description,
            unit=command.unit,
            enabled=command.enabled,
            acquisition_json=dict(command.acquisition_json),
            publish_json=dict(command.publish_json),
            tags_json=dict(command.tags_json),
        )

        async with self._unit_of_work as unit_of_work:
            if (
                await unit_of_work.sources.get(
                    point.tenant_code,
                    point.asset_code,
                    point.agent_code,
                    point.source_code,
                )
                is None
            ):
                raise SourceNotFoundError(
                    point.tenant_code,
                    point.asset_code,
                    point.agent_code,
                    point.source_code,
                )
            if await unit_of_work.points.get_by_id(point.tenant_code, point.point_code):
                raise DuplicatePointError(point.tenant_code, "point_id", point.point_code)
            if (
                await unit_of_work.points.get_by_key(
                    point.tenant_code,
                    point.asset_code,
                    point.agent_code,
                    point.source_code,
                    point.point_key,
                )
                is not None
            ):
                raise DuplicatePointError(
                    point.tenant_code,
                    "point_key",
                    point.point_key,
                )
            if (
                await unit_of_work.points.get_by_ref(
                    point.tenant_code,
                    point.asset_code,
                    point.agent_code,
                    point.source_code,
                    point.point_ref,
                )
                is not None
            ):
                raise DuplicatePointError(
                    point.tenant_code,
                    "point_ref",
                    point.point_ref,
                )
            await unit_of_work.points.add(point)
            await unit_of_work.commit()

        return point


class UpdatePoint:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdatePointCommand) -> Point:
        async with self._unit_of_work as unit_of_work:
            existing = await unit_of_work.points.get_by_id(
                command.tenant_code,
                command.point_code,
            )
            if existing is None:
                raise PointNotFoundError(command.tenant_code, command.point_code)

            duplicate_key = await unit_of_work.points.get_by_key(
                existing.tenant_code,
                existing.asset_code,
                existing.agent_code,
                existing.source_code,
                command.point_key,
            )
            if (
                duplicate_key is not None
                and duplicate_key.point_code != existing.point_code
            ):
                raise DuplicatePointError(
                    existing.tenant_code,
                    "point_key",
                    command.point_key,
                )

            duplicate_ref = await unit_of_work.points.get_by_ref(
                existing.tenant_code,
                existing.asset_code,
                existing.agent_code,
                existing.source_code,
                command.point_ref,
            )
            if (
                duplicate_ref is not None
                and duplicate_ref.point_code != existing.point_code
            ):
                raise DuplicatePointError(
                    existing.tenant_code,
                    "point_ref",
                    command.point_ref,
                )

            point = replace(
                existing,
                point_key=command.point_key,
                point_ref=command.point_ref,
                name=command.name,
                value_type=command.value_type,
                value_model=command.value_model,
                signal_type=command.signal_type,
                description=command.description,
                unit=command.unit,
                enabled=command.enabled,
                acquisition_json=dict(command.acquisition_json),
                publish_json=dict(command.publish_json),
                tags_json=dict(command.tags_json),
                updated_at=utc_now(),
            )
            await unit_of_work.points.update(point)
            await unit_of_work.commit()
        return point


class DeletePoint:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeletePointCommand) -> None:
        async with self._unit_of_work as unit_of_work:
            point = await unit_of_work.points.get_by_id(
                command.tenant_code,
                command.point_code,
            )
            if point is None or not _point_matches_delete_scope(point, command):
                raise PointNotFoundError(command.tenant_code, command.point_code)
            await unit_of_work.points.delete(command.tenant_code, command.point_code)
            await unit_of_work.commit()


def _point_matches_delete_scope(point: Point, command: DeletePointCommand) -> bool:
    return (
        (command.asset_code is None or point.asset_code == command.asset_code)
        and (command.agent_code is None or point.agent_code == command.agent_code)
        and (command.source_code is None or point.source_code == command.source_code)
    )


class ListPoints:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> list[Point]:
        async with self._unit_of_work as unit_of_work:
            if (
                await unit_of_work.sources.get(
                    tenant_code,
                    asset_code,
                    agent_code,
                    source_code,
                )
                is None
            ):
                raise SourceNotFoundError(tenant_code, asset_code, agent_code, source_code)
            return await unit_of_work.points.list_for_source(
                tenant_code,
                asset_code,
                agent_code,
                source_code,
            )
