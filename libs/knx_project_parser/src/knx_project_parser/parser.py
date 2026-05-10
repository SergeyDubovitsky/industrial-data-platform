from __future__ import annotations

import logging
import re
from contextlib import ExitStack
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, is_zipfile

from knx_project_parser.models import (
    Area,
    CommunicationObject,
    Device,
    GroupAddress,
    KnxProject,
    Line,
    LinkedGroupAddress,
    ProjectMetadata,
)

NS = {"knx": "http://knx.org/xml/project/20"}
APP_FILE_PATTERN = re.compile(r"(^|/)(M-[^/]+_A-[^/]+)\.xml$")
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _ObjectDefinition:
    text: str | None = None
    name: str | None = None
    function_text: str | None = None
    datapoint_type: str | None = None
    object_size: str | None = None


@dataclass(slots=True)
class _ProductDefinition:
    product_name: str | None = None
    order_number: str | None = None


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _short_object_id(full_id: str) -> str:
    marker = "_O-"
    if marker not in full_id:
        return full_id
    return full_id[full_id.index(marker) + 1 :]


def _loaded_flags(element: ET.Element) -> dict[str, bool]:
    return {
        key: value == "true"
        for key, value in element.attrib.items()
        if key.endswith("Loaded")
    }


def _format_group_address(address: int, style: str | None) -> str:
    if style == "TwoLevel":
        return f"{address >> 11}/{address & 0x7FF}"
    if style == "FreeLevel":
        return str(address)
    return f"{address >> 11}/{(address >> 8) & 0x07}/{address & 0xFF}"


def _read_xml(archive: ZipFile, member: str, password: bytes | None = None) -> ET.Element:
    return ET.fromstring(archive.read(member, pwd=password))


def _project_member(project_root: str, member_name: str) -> str:
    return f"{project_root}/{member_name}" if project_root else member_name


class KnxProjectParser:
    def parse(self, path: str | Path, password: str | bytes | None = None) -> KnxProject:
        archive_path = Path(path)
        if not archive_path.exists():
            raise FileNotFoundError(f"Project file not found: {archive_path}")
        if not is_zipfile(archive_path):
            raise ValueError(f"Not a valid .knxproj ZIP archive: {archive_path}")

        archive_password = password.encode() if isinstance(password, str) else password

        with ExitStack() as stack:
            archive = stack.enter_context(ZipFile(archive_path))
            project_archive, project_root, is_nested_project_archive = self._open_project_archive(
                stack=stack,
                archive=archive,
                password=archive_password,
            )
            metadata = self._parse_metadata(project_archive, project_root, archive_password)
            runtime_root = _read_xml(
                project_archive,
                _project_member(project_root, "0.xml"),
                password=archive_password,
            )
            medium_names = self._parse_medium_types(archive, archive_password)
            group_addresses = self._parse_group_addresses(runtime_root, metadata.group_address_style)
            group_address_by_short_id = {
                group_address.id.split("_")[-1]: group_address for group_address in group_addresses
            }
            product_definitions, application_refs = self._parse_hardware_catalogs(archive, archive_password)
            application_files = self._collect_application_files(archive)
            self._validate_nested_archive_metadata(
                runtime_root=runtime_root,
                medium_names=medium_names,
                product_definitions=product_definitions,
                is_nested_project_archive=is_nested_project_archive,
            )
            object_definitions_cache: dict[str, dict[str, _ObjectDefinition]] = {}
            areas = self._parse_areas(
                runtime_root=runtime_root,
                medium_names=medium_names,
                group_address_by_short_id=group_address_by_short_id,
                product_definitions=product_definitions,
                application_refs=application_refs,
                application_files=application_files,
                object_definitions_cache=object_definitions_cache,
                archive=archive,
                password=archive_password,
            )
            self._warn_about_unassigned_devices(runtime_root)
        return KnxProject(metadata=metadata, areas=areas, group_addresses=group_addresses)

    def _open_project_archive(
        self,
        stack: ExitStack,
        archive: ZipFile,
        password: bytes | None,
    ) -> tuple[ZipFile, str, bool]:
        project_root = self._find_project_root(archive)
        if project_root is not None:
            return archive, project_root, False

        for name in archive.namelist():
            if not re.fullmatch(r"P-[^/]+\.zip", Path(name).name):
                continue
            nested_bytes = archive.read(name, pwd=password)
            nested_archive = stack.enter_context(ZipFile(BytesIO(nested_bytes)))
            nested_root = self._find_project_root(nested_archive)
            if nested_root is not None:
                return nested_archive, nested_root, True

        raise ValueError("Archive does not contain a project.xml file")

    def _find_project_root(self, archive: ZipFile) -> str | None:
        if "project.xml" in archive.namelist():
            return ""
        for name in archive.namelist():
            if name.endswith("/project.xml"):
                return name.rsplit("/", 1)[0]
        return None

    def _parse_metadata(
        self,
        archive: ZipFile,
        project_root: str,
        password: bytes | None,
    ) -> ProjectMetadata:
        root = _read_xml(archive, _project_member(project_root, "project.xml"), password=password)
        project = root.find("knx:Project", NS)
        if project is None:
            raise ValueError("project.xml does not contain a Project node")
        info = project.find("knx:ProjectInformation", NS)
        if info is None:
            raise ValueError("project.xml does not contain ProjectInformation")
        return ProjectMetadata(
            id=project.attrib["Id"],
            name=info.attrib.get("Name", ""),
            created_by=root.attrib.get("CreatedBy", ""),
            tool_version=root.attrib.get("ToolVersion", ""),
            group_address_style=_strip(info.attrib.get("GroupAddressStyle")),
            last_modified=_strip(info.attrib.get("LastModified")),
            project_start=_strip(info.attrib.get("ProjectStart")),
            completion_status=_strip(info.attrib.get("CompletionStatus")),
            guid=_strip(info.attrib.get("Guid")),
        )

    def _parse_medium_types(self, archive: ZipFile, password: bytes | None) -> dict[str, str]:
        if "knx_master.xml" not in archive.namelist():
            return {}
        root = _read_xml(archive, "knx_master.xml", password=password)
        return {
            medium.attrib["Id"]: medium.attrib.get("Text") or medium.attrib.get("Name", "")
            for medium in root.findall(".//knx:MediumType", NS)
        }

    def _parse_group_addresses(
        self,
        runtime_root: ET.Element,
        group_address_style: str | None,
    ) -> list[GroupAddress]:
        project = runtime_root.find("knx:Project", NS)
        if project is None:
            raise ValueError("0.xml does not contain a Project node")
        container = project.find(".//knx:GroupAddresses", NS)
        if container is None:
            return []

        group_addresses: list[GroupAddress] = []

        def walk(element: ET.Element, range_path: list[str]) -> None:
            for child in element:
                tag = _local_name(child.tag)
                if tag == "GroupRange":
                    next_path = [*range_path]
                    range_name = _strip(child.attrib.get("Name"))
                    if range_name is not None:
                        next_path.append(range_name)
                    walk(child, next_path)
                elif tag == "GroupAddress":
                    address = int(child.attrib["Address"])
                    group_addresses.append(
                        GroupAddress(
                            id=child.attrib["Id"],
                            address=address,
                            address_text=_format_group_address(address, group_address_style),
                            name=child.attrib.get("Name", ""),
                            datapoint_type=_strip(child.attrib.get("DatapointType")),
                            range_path=list(range_path),
                        )
                    )
                else:
                    walk(child, range_path)

        walk(container, [])
        return group_addresses

    def _parse_hardware_catalogs(
        self,
        archive: ZipFile,
        password: bytes | None,
    ) -> tuple[dict[str, _ProductDefinition], dict[str, str]]:
        product_definitions: dict[str, _ProductDefinition] = {}
        application_refs: dict[str, str] = {}
        for name in archive.namelist():
            if not name.endswith("/Hardware.xml"):
                continue
            root = _read_xml(archive, name, password=password)
            for product in root.findall(".//knx:Product", NS):
                product_definitions[product.attrib["Id"]] = _ProductDefinition(
                    product_name=_strip(product.attrib.get("Text")),
                    order_number=_strip(product.attrib.get("OrderNumber")),
                )
            for hardware2program in root.findall(".//knx:Hardware2Program", NS):
                app_ref = hardware2program.find("knx:ApplicationProgramRef", NS)
                if app_ref is not None:
                    application_refs[hardware2program.attrib["Id"]] = app_ref.attrib["RefId"]
        return product_definitions, application_refs

    def _collect_application_files(self, archive: ZipFile) -> dict[str, str]:
        application_files: dict[str, str] = {}
        for name in archive.namelist():
            match = APP_FILE_PATTERN.search(name)
            if match is not None:
                application_files[match.group(2)] = name
        return application_files

    def _validate_nested_archive_metadata(
        self,
        runtime_root: ET.Element,
        medium_names: dict[str, str],
        product_definitions: dict[str, _ProductDefinition],
        is_nested_project_archive: bool,
    ) -> None:
        if not is_nested_project_archive:
            return

        missing_medium_type_ref_ids = sorted(
            {
                medium_type_ref_id
                for line in runtime_root.findall(".//knx:Line", NS)
                if (medium_type_ref_id := _strip(line.attrib.get("MediumTypeRefId"))) is not None
                and medium_type_ref_id not in medium_names
            }
        )
        missing_product_ref_ids = sorted(
            {
                product_ref_id
                for device in runtime_root.findall(".//knx:DeviceInstance", NS)
                if (product_ref_id := device.attrib.get("ProductRefId")) not in product_definitions
            }
        )
        if not missing_medium_type_ref_ids and not missing_product_ref_ids:
            return

        problems: list[str] = []
        if missing_medium_type_ref_ids:
            problems.append(
                "missing medium definitions for "
                + ", ".join(missing_medium_type_ref_ids[:5])
                + (" ..." if len(missing_medium_type_ref_ids) > 5 else "")
            )
        if missing_product_ref_ids:
            problems.append(
                "missing product definitions for "
                + ", ".join(missing_product_ref_ids[:5])
                + (" ..." if len(missing_product_ref_ids) > 5 else "")
            )
        raise ValueError(
            "Nested project archive requires supporting metadata in the outer archive; "
            + "; ".join(problems)
        )

    def _warn_about_unassigned_devices(self, runtime_root: ET.Element) -> None:
        unassigned_devices = runtime_root.findall(".//knx:UnassignedDevices/knx:DeviceInstance", NS)
        if not unassigned_devices:
            return

        samples = []
        for device in unassigned_devices[:5]:
            description = _strip(device.attrib.get("Description")) or device.attrib["Id"]
            samples.append(description)
        LOGGER.warning(
            "Skipping %s unassigned KNX devices that are not attached to any line: %s%s",
            len(unassigned_devices),
            ", ".join(samples),
            " ..." if len(unassigned_devices) > 5 else "",
        )

    def _load_object_definitions(
        self,
        archive: ZipFile,
        application_id: str | None,
        application_files: dict[str, str],
        object_definitions_cache: dict[str, dict[str, _ObjectDefinition]],
        password: bytes | None,
    ) -> dict[str, _ObjectDefinition]:
        if application_id is None:
            return {}
        cached = object_definitions_cache.get(application_id)
        if cached is not None:
            return cached

        file_name = application_files.get(application_id)
        if file_name is None:
            object_definitions_cache[application_id] = {}
            return {}

        root = _read_xml(archive, file_name, password=password)
        definitions: dict[str, _ObjectDefinition] = {}
        for tag_name in ("ComObjectRef", "ComObject"):
            for element in root.findall(f".//knx:{tag_name}", NS):
                short_id = _short_object_id(element.attrib.get("Id", ""))
                if not short_id:
                    continue
                definition = _ObjectDefinition(
                    text=_strip(element.attrib.get("Text")),
                    name=_strip(element.attrib.get("Name")),
                    function_text=_strip(element.attrib.get("FunctionText")),
                    datapoint_type=_strip(element.attrib.get("DatapointType")),
                    object_size=_strip(element.attrib.get("ObjectSize")),
                )
                definitions[short_id] = definition
                if "_R-" in short_id:
                    definitions.setdefault(short_id.split("_R-", 1)[0], definition)

        object_definitions_cache[application_id] = definitions
        return definitions

    def _parse_areas(
        self,
        runtime_root: ET.Element,
        medium_names: dict[str, str],
        group_address_by_short_id: dict[str, GroupAddress],
        product_definitions: dict[str, _ProductDefinition],
        application_refs: dict[str, str],
        application_files: dict[str, str],
        object_definitions_cache: dict[str, dict[str, _ObjectDefinition]],
        archive: ZipFile,
        password: bytes | None,
    ) -> list[Area]:
        project = runtime_root.find("knx:Project", NS)
        if project is None:
            raise ValueError("0.xml does not contain a Project node")

        areas: list[Area] = []
        for area_element in project.findall(".//knx:Area", NS):
            area_address = int(area_element.attrib["Address"])
            area = Area(
                id=area_element.attrib["Id"],
                address=area_address,
                name=area_element.attrib.get("Name", ""),
            )
            for line_element in area_element.findall("knx:Line", NS):
                line_address = int(line_element.attrib["Address"])
                medium_type_ref_id = _strip(line_element.attrib.get("MediumTypeRefId"))
                line = Line(
                    id=line_element.attrib["Id"],
                    address=line_address,
                    name=line_element.attrib.get("Name", ""),
                    medium_type_ref_id=medium_type_ref_id,
                    medium_type_name=medium_names.get(medium_type_ref_id or "", None),
                )
                for device_element in line_element.findall("knx:DeviceInstance", NS):
                    product_ref_id = device_element.attrib["ProductRefId"]
                    application_id = application_refs.get(device_element.attrib["Hardware2ProgramRefId"])
                    object_definitions = self._load_object_definitions(
                        archive=archive,
                        application_id=application_id,
                        application_files=application_files,
                        object_definitions_cache=object_definitions_cache,
                        password=password,
                    )
                    product_definition = product_definitions.get(product_ref_id, _ProductDefinition())
                    device_address = _strip(device_element.attrib.get("Address"))
                    device = Device(
                        id=device_element.attrib["Id"],
                        individual_address=(
                            f"{area_address}.{line_address}.{device_address}"
                            if device_address is not None
                            else None
                        ),
                        name=_strip(device_element.attrib.get("Name")),
                        product_ref_id=product_ref_id,
                        hardware2program_ref_id=device_element.attrib["Hardware2ProgramRefId"],
                        product_name=product_definition.product_name,
                        order_number=product_definition.order_number,
                        serial_number=_strip(device_element.attrib.get("SerialNumber")),
                        last_download=_strip(device_element.attrib.get("LastDownload")),
                        loaded_flags=_loaded_flags(device_element),
                        communication_objects=self._parse_communication_objects(
                            device_element=device_element,
                            group_address_by_short_id=group_address_by_short_id,
                            object_definitions=object_definitions,
                        ),
                    )
                    line.devices.append(device)
                area.lines.append(line)
            areas.append(area)
        return areas

    def _parse_communication_objects(
        self,
        device_element: ET.Element,
        group_address_by_short_id: dict[str, GroupAddress],
        object_definitions: dict[str, _ObjectDefinition],
    ) -> list[CommunicationObject]:
        container = device_element.find("knx:ComObjectInstanceRefs", NS)
        if container is None:
            return []

        communication_objects: list[CommunicationObject] = []
        for instance in container.findall("knx:ComObjectInstanceRef", NS):
            ref_id = instance.attrib["RefId"]
            definition = object_definitions.get(ref_id) or object_definitions.get(ref_id.split("_R-", 1)[0])
            communication_objects.append(
                CommunicationObject(
                    ref_id=ref_id,
                    text=_strip(instance.attrib.get("Text"))
                    or (definition.text if definition is not None else None)
                    or (definition.name if definition is not None else None),
                    function_text=definition.function_text if definition is not None else None,
                    object_size=definition.object_size if definition is not None else None,
                    datapoint_type=_strip(instance.attrib.get("DatapointType"))
                    or (definition.datapoint_type if definition is not None else None),
                    linked_group_addresses=[
                        LinkedGroupAddress(
                            id=group_address.id,
                            address=group_address.address,
                            address_text=group_address.address_text,
                            name=group_address.name,
                            datapoint_type=group_address.datapoint_type,
                        )
                        for link_id in instance.attrib.get("Links", "").split()
                        if (group_address := group_address_by_short_id.get(link_id)) is not None
                    ],
                )
            )
        return communication_objects


def parse_knxproj(path: str | Path, password: str | bytes | None = None) -> KnxProject:
    return KnxProjectParser().parse(path, password=password)
