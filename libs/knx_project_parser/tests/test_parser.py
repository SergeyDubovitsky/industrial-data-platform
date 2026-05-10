from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

from knx_project_parser.cli import main
from knx_project_parser.parser import parse_knxproj

PROJECT_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX CreatedBy="ETS6" ToolVersion="6.3.0" xmlns="http://knx.org/xml/project/20">
  <Project Id="P-TEST">
    <ProjectInformation
      Name="Fixture Project"
      GroupAddressStyle="ThreeLevel"
      LastModified="2026-03-27T10:00:00Z"
      ProjectStart="2026-03-20T10:00:00Z"
      CompletionStatus="Editing"
      Guid="fixture-guid"
    />
  </Project>
</KNX>
"""


RUNTIME_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX CreatedBy="ETS6" ToolVersion="6.3.0" xmlns="http://knx.org/xml/project/20">
  <Project Id="P-TEST">
    <Installations>
      <Installation DefaultLine="P-TEST-0_L-1">
        <Topology>
          <Area Id="P-TEST-0_A-1" Address="1" Name="Area 1">
            <Line Id="P-TEST-0_L-1" Address="1" Name="Line 1" MediumTypeRefId="MT-0">
              <DeviceInstance
                Id="P-TEST-0_DI-1"
                Address="10"
                Name="Wall Panel"
                ProductRefId="M-0001_H-DEVICE_P-0001"
                Hardware2ProgramRefId="M-0001_H-DEVICE_HP-0001"
                SerialNumber="ABC123"
                ApplicationProgramLoaded="true"
                ParametersLoaded="true"
              >
                <ComObjectInstanceRefs>
                  <ComObjectInstanceRef RefId="O-1_R-1" Links="GA-1" />
                </ComObjectInstanceRefs>
              </DeviceInstance>
            </Line>
          </Area>
        </Topology>
        <GroupAddresses>
          <GroupRanges>
            <GroupRange Id="P-TEST-0_GR-1" Name="Lighting">
              <GroupAddress
                Id="P-TEST-0_GA-1"
                Address="2048"
                Name="Switch"
                DatapointType="DPST-1-1"
              />
            </GroupRange>
          </GroupRanges>
        </GroupAddresses>
      </Installation>
    </Installations>
  </Project>
</KNX>
"""


HARDWARE_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-0001">
      <Hardware>
        <Hardware Id="M-0001_H-DEVICE">
          <Products>
            <Product
              Id="M-0001_H-DEVICE_P-0001"
              Text="Fixture Device"
              OrderNumber="0001"
            />
          </Products>
          <Hardware2Programs>
            <Hardware2Program Id="M-0001_H-DEVICE_HP-0001">
              <ApplicationProgramRef RefId="M-0001_A-0001" />
            </Hardware2Program>
          </Hardware2Programs>
        </Hardware>
      </Hardware>
    </Manufacturer>
  </ManufacturerData>
</KNX>
"""


APPLICATION_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <ManufacturerData>
    <Manufacturer RefId="M-0001">
      <ApplicationPrograms>
        <ApplicationProgram Id="M-0001_A-0001">
          <Static>
            <Code>
              <ComObjectRefs>
                <ComObjectRef
                  Id="M-0001_A-0001_O-1_R-1"
                  RefId="M-0001_A-0001_O-1"
                  Text="Switch object"
                  FunctionText="Switching"
                  ObjectSize="1 Bit"
                  DatapointType="DPST-1-1"
                />
              </ComObjectRefs>
            </Code>
          </Static>
        </ApplicationProgram>
      </ApplicationPrograms>
    </Manufacturer>
  </ManufacturerData>
</KNX>
"""


MASTER_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX xmlns="http://knx.org/xml/project/20">
  <MasterData>
    <MediumTypes>
      <MediumType Id="MT-0" Name="TP" Text="Twisted Pair" />
    </MediumTypes>
  </MasterData>
</KNX>
"""


NESTED_PROJECT_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX CreatedBy="ETS6" ToolVersion="6.3.0" xmlns="http://knx.org/xml/project/20">
  <Project Id="P-NESTED">
    <ProjectInformation Name="Nested Project" GroupAddressStyle="ThreeLevel" />
  </Project>
</KNX>
"""


NESTED_RUNTIME_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX CreatedBy="ETS6" ToolVersion="6.3.0" xmlns="http://knx.org/xml/project/20">
  <Project Id="P-NESTED">
    <Installations>
      <Installation>
        <Topology>
          <Area Id="P-NESTED-0_A-1" Address="1" Name="Area">
            <Line Id="P-NESTED-0_L-1" Address="1" Name="Line" MediumTypeRefId="MT-0">
              <DeviceInstance
                Id="P-NESTED-0_DI-1"
                Name="No Address Device"
                ProductRefId="M-0001_H-DEVICE_P-0001"
                Hardware2ProgramRefId="M-0001_H-DEVICE_HP-0001"
              />
            </Line>
          </Area>
        </Topology>
      </Installation>
    </Installations>
  </Project>
</KNX>
"""


UNASSIGNED_RUNTIME_XML = """<?xml version="1.0" encoding="utf-8"?>
<KNX CreatedBy="ETS6" ToolVersion="6.3.0" xmlns="http://knx.org/xml/project/20">
  <Project Id="P-WARN">
    <Installations>
      <Installation>
        <Topology>
          <Area Id="P-WARN-0_A-1" Address="1" Name="Area">
            <Line Id="P-WARN-0_L-1" Address="1" Name="Line" MediumTypeRefId="MT-0">
              <DeviceInstance
                Id="P-WARN-0_DI-1"
                Address="1"
                Name="Assigned Device"
                ProductRefId="M-0001_H-DEVICE_P-0001"
                Hardware2ProgramRefId="M-0001_H-DEVICE_HP-0001"
              />
            </Line>
          </Area>
          <UnassignedDevices>
            <DeviceInstance
              Id="P-WARN-0_DI-2"
              Name=""
              ProductRefId="M-0001_H-DEVICE_P-0001"
              Hardware2ProgramRefId="M-0001_H-DEVICE_HP-0001"
              Description="[UNASSIGNED]"
            />
          </UnassignedDevices>
        </Topology>
      </Installation>
    </Installations>
  </Project>
</KNX>
"""


def _write_base_fixture(archive_path: Path) -> None:
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("P-TEST/project.xml", PROJECT_XML)
        archive.writestr("P-TEST/0.xml", RUNTIME_XML)
        archive.writestr("M-0001/Hardware.xml", HARDWARE_XML)
        archive.writestr("M-0001/M-0001_A-0001.xml", APPLICATION_XML)
        archive.writestr("knx_master.xml", MASTER_XML)


def test_parse_fixture_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "fixture.knxproj"
    _write_base_fixture(archive_path)

    project = parse_knxproj(archive_path)

    assert project.metadata.name == "Fixture Project"
    assert project.group_addresses[0].address_text == "1/0/0"
    assert project.group_addresses[0].range_path == ["Lighting"]
    assert project.areas[0].lines[0].medium_type_name == "Twisted Pair"

    device = project.areas[0].lines[0].devices[0]
    assert device.individual_address == "1.1.10"
    assert device.product_name == "Fixture Device"
    assert device.loaded_flags["ApplicationProgramLoaded"] is True

    com_object = device.communication_objects[0]
    assert com_object.text == "Switch object"
    assert com_object.function_text == "Switching"
    assert com_object.linked_group_addresses[0].name == "Switch"


def test_parse_archive_with_nested_project_zip(tmp_path: Path) -> None:
    archive_path = tmp_path / "nested.knxproj"
    nested_zip_path = tmp_path / "P-AAAA.zip"
    with ZipFile(nested_zip_path, "w") as nested_archive:
        nested_archive.writestr("project.xml", NESTED_PROJECT_XML)
        nested_archive.writestr("0.xml", NESTED_RUNTIME_XML)

    with ZipFile(archive_path, "w") as archive:
        archive.writestr("P-AAAA.zip", nested_zip_path.read_bytes())
        archive.writestr("knx_master.xml", MASTER_XML)
        archive.writestr("M-0001/Hardware.xml", HARDWARE_XML)

    project = parse_knxproj(archive_path)

    assert project.metadata.name == "Nested Project"
    assert project.areas[0].lines[0].medium_type_name == "Twisted Pair"
    assert project.areas[0].lines[0].devices[0].individual_address is None


def test_nested_archive_without_outer_metadata_fails(tmp_path: Path) -> None:
    archive_path = tmp_path / "nested-missing-metadata.knxproj"
    nested_zip_path = tmp_path / "P-BBBB.zip"
    with ZipFile(nested_zip_path, "w") as nested_archive:
        nested_archive.writestr("project.xml", NESTED_PROJECT_XML)
        nested_archive.writestr("0.xml", NESTED_RUNTIME_XML)
        nested_archive.writestr("knx_master.xml", MASTER_XML)
        nested_archive.writestr("M-0001/Hardware.xml", HARDWARE_XML)

    with ZipFile(archive_path, "w") as archive:
        archive.writestr("P-BBBB.zip", nested_zip_path.read_bytes())

    with pytest.raises(ValueError, match="Nested project archive requires supporting metadata"):
        parse_knxproj(archive_path)


def test_parse_logs_warning_for_unassigned_devices(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    archive_path = tmp_path / "warn.knxproj"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("P-WARN/project.xml", PROJECT_XML.replace("P-TEST", "P-WARN"))
        archive.writestr("P-WARN/0.xml", UNASSIGNED_RUNTIME_XML)
        archive.writestr("M-0001/Hardware.xml", HARDWARE_XML)
        archive.writestr("M-0001/M-0001_A-0001.xml", APPLICATION_XML)
        archive.writestr("knx_master.xml", MASTER_XML)

    caplog.set_level("WARNING", logger="knx_project_parser.parser")
    project = parse_knxproj(archive_path)

    assert len(project.areas[0].lines[0].devices) == 1
    assert "Skipping 1 unassigned KNX devices" in caplog.text


def test_cli_outputs_yaml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    archive_path = tmp_path / "fixture.knxproj"
    _write_base_fixture(archive_path)

    main([str(archive_path)])
    output = capsys.readouterr().out

    assert output.startswith("metadata:\n")
    assert not output.lstrip().startswith("{")
    assert yaml.safe_load(output)["metadata"]["name"] == "Fixture Project"
