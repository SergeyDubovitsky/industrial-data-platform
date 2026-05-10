from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class ProjectMetadata:
    id: str
    name: str
    created_by: str
    tool_version: str
    group_address_style: str | None = None
    last_modified: str | None = None
    project_start: str | None = None
    completion_status: str | None = None
    guid: str | None = None


@dataclass(slots=True)
class LinkedGroupAddress:
    id: str
    address: int
    address_text: str
    name: str
    datapoint_type: str | None = None


@dataclass(slots=True)
class CommunicationObject:
    ref_id: str
    text: str | None = None
    function_text: str | None = None
    object_size: str | None = None
    datapoint_type: str | None = None
    linked_group_addresses: list[LinkedGroupAddress] = field(default_factory=list)


@dataclass(slots=True)
class Device:
    id: str
    individual_address: str | None
    name: str | None
    product_ref_id: str
    hardware2program_ref_id: str
    product_name: str | None = None
    order_number: str | None = None
    serial_number: str | None = None
    last_download: str | None = None
    loaded_flags: dict[str, bool] = field(default_factory=dict)
    communication_objects: list[CommunicationObject] = field(default_factory=list)


@dataclass(slots=True)
class Line:
    id: str
    address: int
    name: str
    medium_type_ref_id: str | None = None
    medium_type_name: str | None = None
    devices: list[Device] = field(default_factory=list)


@dataclass(slots=True)
class Area:
    id: str
    address: int
    name: str
    lines: list[Line] = field(default_factory=list)


@dataclass(slots=True)
class GroupAddress:
    id: str
    address: int
    address_text: str
    name: str
    datapoint_type: str | None = None
    range_path: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KnxProject:
    metadata: ProjectMetadata
    areas: list[Area] = field(default_factory=list)
    group_addresses: list[GroupAddress] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
