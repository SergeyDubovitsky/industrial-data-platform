from __future__ import annotations

import asyncio
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import uvicorn
from playwright.sync_api import Locator, Page, expect

from idp_config_registry.infrastructure.backoffice_selectors import (
    AgentSelection,
    AssetSelection,
    SourceSelection,
    encode_agent_selection,
    encode_asset_selection,
    encode_source_selection,
)
from idp_config_registry.main import create_app
from idp_config_registry.settings import ConfigRegistrySettings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.integration_backoffice_ui,
]


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    return {
        **browser_context_args,
        "viewport": {"width": 1440, "height": 1000},
    }


@pytest.fixture(scope="module")
def config_registry_backoffice_url(
    local_config_registry_postgres_stack: Any,
) -> Iterator[str]:
    port = _reserve_free_port()
    app = create_app(
        settings=ConfigRegistrySettings(
            internal_mode=True,
            database_url=local_config_registry_postgres_stack.database_url,
        )
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="on",
        )
    )
    errors: list[BaseException] = []

    def run_server() -> None:
        try:
            asyncio.run(server.serve())
        except BaseException as exc:  # pragma: no cover - raised in fixture teardown
            errors.append(exc)

    thread = threading.Thread(
        target=run_server,
        name="config-registry-backoffice-ui",
        daemon=True,
    )
    thread.start()
    base_url = f"http://127.0.0.1:{port}"

    try:
        _wait_for_ready(base_url, thread=thread, errors=errors)
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            server.force_exit = True
            thread.join(timeout=10)
        if thread.is_alive():
            raise AssertionError("Config Registry UI test server did not stop cleanly")
        if errors:
            raise AssertionError("Config Registry UI test server failed") from errors[0]


def test_backoffice_browser_crud_pages_and_mutable_entity_flows(
    config_registry_backoffice_url: str,
    page: Page,
) -> None:
    codes = RegistryCodes.unique("crud")

    page.goto(f"{config_registry_backoffice_url}/backoffice")
    expect(page).to_have_title(re.compile("Config Registry Backoffice"))
    expect(page.get_by_role("link", name="Tenants")).to_be_visible()

    _create_registry_tree(page, config_registry_backoffice_url, codes)
    _open_mutable_detail_pages(page, config_registry_backoffice_url, codes)

    _edit_tenant(page, config_registry_backoffice_url, codes)
    _edit_asset(page, config_registry_backoffice_url, codes)
    _edit_agent(page, config_registry_backoffice_url, codes)
    _edit_source(page, config_registry_backoffice_url, codes)
    _edit_point(page, config_registry_backoffice_url, codes)

    _create_and_delete_mutable_entities(page, config_registry_backoffice_url, codes)


def test_backoffice_browser_config_revision_and_outbox_flows(
    config_registry_backoffice_url: str,
    page: Page,
) -> None:
    codes = RegistryCodes.unique("cfg")
    _create_registry_tree(page, config_registry_backoffice_url, codes)

    _create_agent_runtime_revision(page, config_registry_backoffice_url, codes)
    _create_source_config_revision(page, config_registry_backoffice_url, codes)
    _open_config_revision_detail_pages(page, config_registry_backoffice_url, codes)
    _assert_append_only_views_do_not_expose_edit_or_delete(
        page,
        config_registry_backoffice_url,
        codes,
    )

    rendered_revision = _render_agent_config(page, config_registry_backoffice_url, codes)
    _assert_outbox_record_visible(
        page,
        config_registry_backoffice_url,
        codes,
        rendered_revision,
    )


@dataclass(frozen=True)
class RegistryCodes:
    prefix: str
    tenant_code: str
    tenant_name: str
    asset_code: str
    asset_name: str
    agent_code: str
    agent_name: str
    source_code: str
    source_name: str
    point_code: str
    point_name: str
    point_key: str
    point_ref: str
    runtime_revision: str
    source_revision: str

    @classmethod
    def unique(cls, scenario: str) -> RegistryCodes:
        suffix = uuid.uuid4().hex[:8]
        prefix = f"ui-{scenario}-{suffix}"
        point_segment = str(int(suffix[:4], 16) % 60000)
        return cls(
            prefix=prefix,
            tenant_code=f"{prefix}-tenant",
            tenant_name=f"{prefix} Tenant",
            asset_code=f"{prefix}-asset",
            asset_name=f"{prefix} Asset",
            agent_code=f"{prefix}-agent",
            agent_name=f"{prefix} Agent",
            source_code=f"{prefix}-source",
            source_name=f"{prefix} Source",
            point_code=f"{prefix}-point",
            point_name=f"{prefix} Point",
            point_key=f"1%2F{point_segment}%2F1",
            point_ref=f"1/{point_segment}/1",
            runtime_revision=f"{prefix}-runtime-rev",
            source_revision=f"{prefix}-source-rev",
        )

    @property
    def tenant_label(self) -> str:
        return f"{self.tenant_name} ({self.tenant_code})"

    @property
    def asset_label(self) -> str:
        return f"{self.tenant_label} / {self.asset_name} ({self.asset_code})"

    @property
    def agent_label(self) -> str:
        return f"{self.asset_label} / {self.agent_name} ({self.agent_code})"

    @property
    def source_label(self) -> str:
        return f"{self.agent_label} / {self.source_name} ({self.source_code})"


def _create_registry_tree(page: Page, base_url: str, codes: RegistryCodes) -> None:
    _create_tenant(page, base_url, codes.tenant_code, codes.tenant_name)
    _create_asset(page, base_url, codes)
    _create_agent(page, base_url, codes)
    _create_source(page, base_url, codes)
    _create_point(page, base_url, codes)


def _create_tenant(page: Page, base_url: str, code: str, name: str) -> None:
    page.goto(f"{base_url}/backoffice/tenant-model/create")
    expect(page.get_by_role("heading", name="New Tenant")).to_be_visible()
    page.get_by_label("Code").fill(code)
    page.get_by_label("Name").fill(name)
    _save(page)
    _expect_list_page(page, "Tenants", code)


def _create_asset(page: Page, base_url: str, codes: RegistryCodes) -> None:
    page.goto(f"{base_url}/backoffice/asset-model/create")
    expect(page.get_by_role("heading", name="New Asset")).to_be_visible()
    tenant_select = page.get_by_label("Tenant", exact=True)
    _expect_select_option(tenant_select, text=codes.tenant_code)
    tenant_select.select_option(value=codes.tenant_code)
    page.get_by_label("Code").fill(codes.asset_code)
    page.get_by_label("Name").fill(codes.asset_name)
    page.get_by_label("Description").fill("Created by Playwright UI coverage")
    _save(page)
    _expect_list_page(page, "Assets", codes.asset_code)


def _create_agent(page: Page, base_url: str, codes: RegistryCodes) -> None:
    page.goto(f"{base_url}/backoffice/agent-model/create")
    expect(page.get_by_role("heading", name="New Agent")).to_be_visible()
    asset_select = page.get_by_label("Asset", exact=True)
    _expect_select_option(
        asset_select,
        text=codes.asset_code,
    )
    asset_select.select_option(
        value=encode_asset_selection(
            AssetSelection(
                tenant_code=codes.tenant_code,
                asset_code=codes.asset_code,
            )
        )
    )
    page.get_by_label("Code").fill(codes.agent_code)
    page.get_by_label("Name").fill(codes.agent_name)
    _save(page)
    _expect_list_page(page, "Agents", codes.agent_code)


def _create_source(page: Page, base_url: str, codes: RegistryCodes) -> None:
    page.goto(f"{base_url}/backoffice/source-model/create")
    expect(page.get_by_role("heading", name="New Source")).to_be_visible()
    agent_select = page.get_by_label("Agent", exact=True)
    _expect_select_option(agent_select, text=codes.agent_code)
    agent_select.select_option(value=_agent_selection_value(codes))
    page.get_by_label("Code").fill(codes.source_code)
    page.get_by_label("Source Type").fill("knx")
    page.get_by_label("Enabled").check()
    page.get_by_label("Name").fill(codes.source_name)
    page.get_by_label("Description").fill("Created by Playwright UI coverage")
    _save(page)
    _expect_list_page(page, "Sources", codes.source_code)


def _create_point(page: Page, base_url: str, codes: RegistryCodes) -> None:
    page.goto(f"{base_url}/backoffice/point-model/create")
    expect(page.get_by_role("heading", name="New Point")).to_be_visible()
    source_select = page.get_by_label("Source", exact=True)
    _expect_select_option(
        source_select,
        text=codes.source_code,
    )
    source_select.select_option(value=_source_selection_value(codes))
    page.get_by_label("Code").fill(codes.point_code)
    page.get_by_label("Point Key").fill(codes.point_key)
    page.get_by_label("Point Ref").fill(codes.point_ref)
    page.get_by_label("Name").fill(codes.point_name)
    page.get_by_label("Description").fill("Created by Playwright UI coverage")
    page.get_by_label("Value Type").fill("number")
    page.get_by_label("Value Model").fill("knx.dpt.9.001")
    page.get_by_label("Signal Type").fill("sensor")
    page.get_by_label("Unit").fill("C")
    page.get_by_label("Enabled").check()
    _save(page)
    _expect_list_page(page, "Points", codes.point_code)


def _open_mutable_detail_pages(
    page: Page,
    base_url: str,
    codes: RegistryCodes,
) -> None:
    detail_pages = [
        ("tenant-model", "Tenants", codes.tenant_code),
        ("asset-model", "Assets", codes.asset_code),
        ("agent-model", "Agents", codes.agent_code),
        ("source-model", "Sources", codes.source_code),
        ("point-model", "Points", codes.point_code),
    ]
    for identity, heading, visible_text in detail_pages:
        _open_row_detail(page, base_url, identity, heading, visible_text)
        expect(page.get_by_text(visible_text)).to_be_visible()


def _edit_tenant(page: Page, base_url: str, codes: RegistryCodes) -> None:
    _open_row_edit(page, base_url, "tenant-model", "Tenants", codes.tenant_code)
    expect(page.get_by_role("heading", name="Edit Tenant")).to_be_visible()
    page.get_by_label("Name").fill(f"{codes.tenant_name} Updated")
    page.get_by_label("Status").fill("disabled")
    _save(page)
    _expect_list_page(page, "Tenants", f"{codes.tenant_name} Updated")


def _edit_asset(page: Page, base_url: str, codes: RegistryCodes) -> None:
    _open_row_edit(page, base_url, "asset-model", "Assets", codes.asset_code)
    expect(page.get_by_role("heading", name="Edit Asset")).to_be_visible()
    expect(page.get_by_label("Tenant", exact=True)).to_be_disabled()
    page.get_by_label("Name").fill(f"{codes.asset_name} Updated")
    page.get_by_label("Description").fill("Updated by Playwright UI coverage")
    page.get_by_label("Status").fill("disabled")
    _save(page)
    _expect_list_page(page, "Assets", f"{codes.asset_name} Updated")


def _edit_agent(page: Page, base_url: str, codes: RegistryCodes) -> None:
    _open_row_edit(page, base_url, "agent-model", "Agents", codes.agent_code)
    expect(page.get_by_role("heading", name="Edit Agent")).to_be_visible()
    expect(page.get_by_label("Asset", exact=True)).to_be_disabled()
    page.get_by_label("Name").fill(f"{codes.agent_name} Updated")
    page.get_by_label("Status").fill("disabled")
    page.get_by_label("Bootstrap Hint Json").fill('{"mode":"playwright"}')
    _save(page)
    _expect_list_page(page, "Agents", f"{codes.agent_name} Updated")


def _edit_source(page: Page, base_url: str, codes: RegistryCodes) -> None:
    _open_row_edit(page, base_url, "source-model", "Sources", codes.source_code)
    expect(page.get_by_role("heading", name="Edit Source")).to_be_visible()
    expect(page.get_by_label("Agent", exact=True)).to_be_disabled()
    page.get_by_label("Source Type").fill("knx")
    page.get_by_label("Enabled").uncheck()
    page.get_by_label("Name").fill(f"{codes.source_name} Updated")
    page.get_by_label("Description").fill("Updated by Playwright UI coverage")
    page.get_by_label("Connection Json").fill('{"host":"127.0.0.1"}')
    page.get_by_label("Acquisition Defaults Json").fill(
        '{"listen":true,"read_on_start":true,"periodic_interval_seconds":60}'
    )
    page.get_by_label("Publish Defaults Json").fill(
        '{"enabled":true,"change_threshold":0.5}'
    )
    _save(page)
    _expect_list_page(page, "Sources", f"{codes.source_name} Updated")


def _edit_point(page: Page, base_url: str, codes: RegistryCodes) -> None:
    _open_row_edit(page, base_url, "point-model", "Points", codes.point_code)
    expect(page.get_by_role("heading", name="Edit Point")).to_be_visible()
    expect(page.get_by_label("Source", exact=True)).to_be_disabled()
    page.get_by_label("Point Key").fill(codes.point_key.replace("%2F1", "%2F2"))
    page.get_by_label("Point Ref").fill(codes.point_ref.removesuffix("/1") + "/2")
    page.get_by_label("Name").fill(f"{codes.point_name} Updated")
    page.get_by_label("Description").fill("Updated by Playwright UI coverage")
    page.get_by_label("Value Type").fill("number")
    page.get_by_label("Value Model").fill("knx.dpt.9.001")
    page.get_by_label("Signal Type").fill("sensor")
    page.get_by_label("Unit").fill("F")
    page.get_by_label("Enabled").uncheck()
    page.get_by_label("Acquisition Json").fill('{"debounce_ms":500}')
    page.get_by_label("Publish Json").fill('{"enabled":true}')
    page.get_by_label("Tags Json").fill('{"room":"lab"}')
    _save(page)
    _expect_list_page(page, "Points", f"{codes.point_name} Updated")


def _create_and_delete_mutable_entities(
    page: Page,
    base_url: str,
    codes: RegistryCodes,
) -> None:
    delete_tenant = f"{codes.prefix}-delete-tenant"
    _create_tenant(page, base_url, delete_tenant, f"{codes.prefix} Delete Tenant")
    _delete_row(page, base_url, "tenant-model", delete_tenant)

    delete_asset = f"{codes.prefix}-delete-asset"
    _create_asset(
        page,
        base_url,
        _replace(codes, asset_code=delete_asset, asset_name=f"{codes.prefix} Delete Asset"),
    )
    _delete_row(
        page,
        base_url,
        "asset-model",
        delete_asset,
    )

    delete_agent = f"{codes.prefix}-delete-agent"
    _create_agent(
        page,
        base_url,
        _replace(codes, agent_code=delete_agent, agent_name=f"{codes.prefix} Delete Agent"),
    )
    _delete_row(
        page,
        base_url,
        "agent-model",
        delete_agent,
    )

    delete_source = f"{codes.prefix}-delete-source"
    _create_source(
        page,
        base_url,
        _replace(
            codes,
            source_code=delete_source,
            source_name=f"{codes.prefix} Delete Source",
        ),
    )
    _delete_row(
        page,
        base_url,
        "source-model",
        delete_source,
    )

    delete_point = f"{codes.prefix}-delete-point"
    delete_point_codes = _replace(
        codes,
        point_code=delete_point,
        point_name=f"{codes.prefix} Delete Point",
        point_key=codes.point_key.replace("%2F1", "%2F3"),
        point_ref=codes.point_ref.removesuffix("/1") + "/3",
    )
    _create_point(page, base_url, delete_point_codes)
    _delete_row(
        page,
        base_url,
        "point-model",
        delete_point,
    )


def _create_agent_runtime_revision(
    page: Page,
    base_url: str,
    codes: RegistryCodes,
) -> None:
    page.goto(f"{base_url}/backoffice/agent-runtime-config-revision-model/create")
    expect(
        page.get_by_role("heading", name="New Agent Runtime Config Revision")
    ).to_be_visible()
    agent_select = page.get_by_label("Agent", exact=True)
    _expect_select_option(agent_select, text=codes.agent_code)
    agent_select.select_option(value=_agent_selection_value(codes))
    page.get_by_label("Config Revision", exact=True).fill(codes.runtime_revision)
    page.get_by_label("Issued At").fill("2026-05-17T12:00:00Z")
    page.get_by_label("Agent Runtime Payload Json").fill('{"demo":true}')
    _save(page)
    _expect_list_page(
        page,
        "Agent Runtime Config Revisions",
        codes.runtime_revision,
    )


def _create_source_config_revision(
    page: Page,
    base_url: str,
    codes: RegistryCodes,
) -> None:
    page.goto(f"{base_url}/backoffice/source-config-revision-model/create")
    expect(page.get_by_role("heading", name="New Source Config Revision")).to_be_visible()
    source_select = page.get_by_label("Source", exact=True)
    _expect_select_option(
        source_select,
        text=codes.source_code,
    )
    source_select.select_option(value=_source_selection_value(codes))
    page.get_by_label("Source Config Revision", exact=True).fill(codes.source_revision)
    page.get_by_label("Config Revision", exact=True).fill(codes.runtime_revision)
    page.get_by_label("Issued At").fill("2026-05-17T12:00:01Z")
    page.get_by_label("Source Payload Json").fill('{"demo":true}')
    _save(page)
    _expect_list_page(page, "Source Config Revisions", codes.source_revision)


def _open_config_revision_detail_pages(
    page: Page,
    base_url: str,
    codes: RegistryCodes,
) -> None:
    _open_row_detail(
        page,
        base_url,
        "agent-runtime-config-revision-model",
        "Agent Runtime Config Revisions",
        codes.runtime_revision,
    )
    expect(page.get_by_text(codes.runtime_revision)).to_be_visible()
    _open_row_detail(
        page,
        base_url,
        "source-config-revision-model",
        "Source Config Revisions",
        codes.source_revision,
    )
    expect(page.get_by_text(codes.source_revision)).to_be_visible()


def _assert_append_only_views_do_not_expose_edit_or_delete(
    page: Page,
    base_url: str,
    codes: RegistryCodes,
) -> None:
    checks = [
        (
            "agent-runtime-config-revision-model",
            "Agent Runtime Config Revisions",
            codes.runtime_revision,
            (
                f"{codes.tenant_code};{codes.asset_code};{codes.agent_code};"
                f"{codes.runtime_revision}"
            ),
        ),
        (
            "source-config-revision-model",
            "Source Config Revisions",
            codes.source_revision,
            (
                f"{codes.tenant_code};{codes.asset_code};{codes.agent_code};"
                f"{codes.source_code};{codes.source_revision}"
            ),
        ),
    ]
    for identity, heading, row_text, pk in checks:
        page.goto(f"{base_url}/backoffice/{identity}/list")
        _expect_list_page(page, heading, row_text)
        row = _row(page, row_text)
        # SQLAdmin icon-only row actions have no stable accessible names.
        expect(row.locator('a[href*="/edit/"]')).to_have_count(0)
        expect(row.locator('[data-bs-target="#modal-delete"]')).to_have_count(0)
        response = page.goto(f"{base_url}/backoffice/{identity}/edit/{pk}")
        assert response is not None
        assert response.status == 403


def _render_agent_config(page: Page, base_url: str, codes: RegistryCodes) -> str:
    _open_row_detail(page, base_url, "agent-model", "Agents", codes.agent_code)
    page.get_by_role("link", name="Собрать config").click()
    expect(
        page.get_by_text("Собрать runtime/source config revision")
    ).to_be_visible()
    page.get_by_role("link", name="Yes").click()
    expect(page.get_by_role("heading", name="Собрать config")).to_be_visible()
    expect(page.get_by_text("Создано записей в config_outbox: 2.")).to_be_visible()
    body_text = page.locator("body").inner_text()
    revision_match = re.search(r"revision=(backoffice-[0-9TZ]+)", body_text)
    assert revision_match is not None
    return revision_match.group(1)


def _assert_outbox_record_visible(
    page: Page,
    base_url: str,
    codes: RegistryCodes,
    rendered_revision: str,
) -> None:
    page.goto(f"{base_url}/backoffice/config-outbox-model/list")
    _expect_list_page(page, "Config Outbox Records", rendered_revision)
    expect(page.get_by_role("link", name=re.compile(r"New Config Outbox Record"))).to_have_count(0)
    row = _row(page, rendered_revision)
    expect(row).to_contain_text(codes.agent_code)
    # SQLAdmin renders the details affordance as an icon-only link.
    row.locator('a[href*="/details/"]').first.click()
    expect(page).to_have_url(re.compile(r"/backoffice/config-outbox-model/details/"))
    expect(page.get_by_text(rendered_revision).first).to_be_visible()
    expect(page.get_by_role("link", name="Edit")).to_have_count(0)
    expect(page.get_by_role("link", name="Delete")).to_have_count(0)
    response = page.goto(f"{base_url}/backoffice/config-outbox-model/create")
    assert response is not None
    assert response.status == 403


def _delete_row(
    page: Page,
    base_url: str,
    identity: str,
    row_text: str,
) -> None:
    page.goto(f"{base_url}/backoffice/{identity}/list")
    row = _row(page, row_text)
    # SQLAdmin delete affordances are icon-only links.
    row.locator('[data-bs-target="#modal-delete"]').click()
    expect(page.get_by_role("heading", name="Please confirm")).to_be_visible()
    page.locator("#modal-delete-button").click()
    expect(page.get_by_role("row").filter(has_text=row_text)).to_have_count(0)


def _expect_list_page(page: Page, heading: str, visible_text: str) -> None:
    expect(page.get_by_role("heading", name=heading)).to_be_visible()
    expect(page.get_by_text(visible_text).first).to_be_visible()


def _save(page: Page) -> None:
    page.get_by_role("button", name="Save", exact=True).click()


def _expect_select_option(select: Locator, *, text: str) -> None:
    expect(select.locator("option").filter(has_text=text)).to_have_count(1)


def _open_row_detail(
    page: Page,
    base_url: str,
    identity: str,
    heading: str,
    row_text: str,
) -> None:
    page.goto(f"{base_url}/backoffice/{identity}/list")
    _expect_list_page(page, heading, row_text)
    # SQLAdmin details affordances are icon-only links with generated UUID PKs.
    _row(page, row_text).locator('a[href*="/details/"]').first.click()


def _open_row_edit(
    page: Page,
    base_url: str,
    identity: str,
    heading: str,
    row_text: str,
) -> None:
    page.goto(f"{base_url}/backoffice/{identity}/list")
    _expect_list_page(page, heading, row_text)
    # SQLAdmin edit affordances are icon-only links with generated UUID PKs.
    _row(page, row_text).locator('a[href*="/edit/"]').first.click()


def _row(page: Page, text: str) -> Locator:
    return page.get_by_role("row").filter(has_text=text).first


def _agent_selection_value(codes: RegistryCodes) -> str:
    return encode_agent_selection(
        AgentSelection(
            tenant_code=codes.tenant_code,
            asset_code=codes.asset_code,
            agent_code=codes.agent_code,
        )
    )


def _source_selection_value(codes: RegistryCodes) -> str:
    return encode_source_selection(
        SourceSelection(
            tenant_code=codes.tenant_code,
            asset_code=codes.asset_code,
            agent_code=codes.agent_code,
            source_code=codes.source_code,
        )
    )


def _replace(codes: RegistryCodes, **changes: str) -> RegistryCodes:
    values = {
        "prefix": codes.prefix,
        "tenant_code": codes.tenant_code,
        "tenant_name": codes.tenant_name,
        "asset_code": codes.asset_code,
        "asset_name": codes.asset_name,
        "agent_code": codes.agent_code,
        "agent_name": codes.agent_name,
        "source_code": codes.source_code,
        "source_name": codes.source_name,
        "point_code": codes.point_code,
        "point_name": codes.point_name,
        "point_key": codes.point_key,
        "point_ref": codes.point_ref,
        "runtime_revision": codes.runtime_revision,
        "source_revision": codes.source_revision,
    }
    values.update(changes)
    return RegistryCodes(**values)


def _reserve_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        return int(sock.getsockname()[1])


def _wait_for_ready(
    base_url: str,
    *,
    thread: threading.Thread,
    errors: list[BaseException],
    timeout: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout
    last_error = "Config Registry app server has not started yet."
    while time.monotonic() < deadline:
        if errors:
            raise AssertionError("Config Registry UI test server failed") from errors[0]
        if not thread.is_alive():
            raise AssertionError("Config Registry UI test server stopped early")
        try:
            with urllib.request.urlopen(f"{base_url}/ready", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(0.2)
    raise AssertionError(
        "Config Registry UI test server did not become ready within "
        f"{timeout:.0f}s. Last error: {last_error}"
    )
