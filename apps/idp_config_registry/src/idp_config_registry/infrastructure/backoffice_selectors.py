from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from sqladmin.fields import SelectField
from wtforms import validators

from idp_config_registry.application.use_cases.agents import ListAgents
from idp_config_registry.application.use_cases.assets import ListAssets
from idp_config_registry.application.use_cases.sources import ListSources
from idp_config_registry.application.use_cases.tenants import ListTenants
from idp_config_registry.infrastructure.backoffice_support import get_current_state

TENANT_SELECTOR_FIELD = "tenant_selector"
ASSET_SELECTOR_FIELD = "asset_selector"
AGENT_SELECTOR_FIELD = "agent_selector"
SOURCE_SELECTOR_FIELD = "source_selector"


@dataclass(frozen=True)
class AssetSelection:
    tenant_code: str
    asset_code: str


@dataclass(frozen=True)
class AgentSelection:
    tenant_code: str
    asset_code: str
    agent_code: str


@dataclass(frozen=True)
class SourceSelection:
    tenant_code: str
    asset_code: str
    agent_code: str
    source_code: str


def bind_select_field(
    form: type,
    *,
    field_name: str,
    label: str,
    choices: list[tuple[str, str]],
    coerce: Callable[[str], object],
    required: bool,
    disabled: bool = False,
) -> None:
    render_kw: dict[str, Any] = {"class": "form-control"}
    if disabled:
        render_kw["disabled"] = True
    field_validators = (
        [validators.InputRequired()] if required else [validators.Optional()]
    )
    setattr(
        form,
        field_name,
        SelectField(
            label,
            choices=choices,
            coerce=coerce,
            validators=field_validators,
            render_kw=render_kw,
        ),
    )


def attach_selector_value(model: Any, *, field_name: str, value: str) -> Any:
    setattr(model, field_name, value)
    return model


def tenant_select_label(tenant_code: str, name: str) -> str:
    if name == tenant_code:
        return tenant_code
    return f"{name} ({tenant_code})"


async def tenant_select_choices() -> list[tuple[str, str]]:
    state = get_current_state()
    tenants = await ListTenants(state.unit_of_work_factory()).execute()
    return [
        (tenant.tenant_code, tenant_select_label(tenant.tenant_code, tenant.name))
        for tenant in tenants
    ]


def asset_select_label(
    tenant_name: str,
    tenant_code: str,
    asset_name: str,
    asset_code: str,
) -> str:
    tenant_label = tenant_select_label(tenant_code, tenant_name)
    if asset_name == asset_code:
        return f"{tenant_label} / {asset_code}"
    return f"{tenant_label} / {asset_name} ({asset_code})"


def encode_asset_selection(selection: AssetSelection) -> str:
    return json.dumps(
        {
            "tenant_id": selection.tenant_code,
            "asset_id": selection.asset_code,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_asset_selection(value: str) -> AssetSelection:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("Asset selection must be a JSON object")
    return AssetSelection(
        tenant_code=str(payload["tenant_id"]),
        asset_code=str(payload["asset_id"]),
    )


async def asset_select_choices() -> list[tuple[str, str]]:
    state = get_current_state()
    tenants = await ListTenants(state.unit_of_work_factory()).execute()
    choices: list[tuple[str, str]] = []
    for tenant in tenants:
        assets = await ListAssets(state.unit_of_work_factory()).execute(tenant.tenant_code)
        for asset in assets:
            choices.append(
                (
                    encode_asset_selection(
                        AssetSelection(
                            tenant_code=tenant.tenant_code,
                            asset_code=asset.asset_code,
                        )
                    ),
                    asset_select_label(
                        tenant.name,
                        tenant.tenant_code,
                        asset.name,
                        asset.asset_code,
                    ),
                )
            )
    return choices


def agent_select_label(
    tenant_name: str,
    tenant_code: str,
    asset_name: str,
    asset_code: str,
    agent_name: str | None,
    agent_code: str,
) -> str:
    asset_label = asset_select_label(tenant_name, tenant_code, asset_name, asset_code)
    if not agent_name or agent_name == agent_code:
        return f"{asset_label} / {agent_code}"
    return f"{asset_label} / {agent_name} ({agent_code})"


def encode_agent_selection(selection: AgentSelection) -> str:
    return json.dumps(
        {
            "tenant_id": selection.tenant_code,
            "asset_id": selection.asset_code,
            "agent_id": selection.agent_code,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_agent_selection(value: str) -> AgentSelection:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("Agent selection must be a JSON object")
    return AgentSelection(
        tenant_code=str(payload["tenant_id"]),
        asset_code=str(payload["asset_id"]),
        agent_code=str(payload["agent_id"]),
    )


async def agent_select_choices() -> list[tuple[str, str]]:
    return await agent_select_choices_for_state(get_current_state())


async def agent_select_choices_for_state(state: Any) -> list[tuple[str, str]]:
    tenants = await ListTenants(state.unit_of_work_factory()).execute()
    choices: list[tuple[str, str]] = []
    for tenant in tenants:
        assets = await ListAssets(state.unit_of_work_factory()).execute(tenant.tenant_code)
        for asset in assets:
            agents = await ListAgents(state.unit_of_work_factory()).execute(
                tenant.tenant_code,
                asset.asset_code,
            )
            for agent in agents:
                choices.append(
                    (
                        encode_agent_selection(
                            AgentSelection(
                                tenant_code=tenant.tenant_code,
                                asset_code=asset.asset_code,
                                agent_code=agent.agent_code,
                            )
                        ),
                        agent_select_label(
                            tenant.name,
                            tenant.tenant_code,
                            asset.name,
                            asset.asset_code,
                            agent.name,
                            agent.agent_code,
                        ),
                    )
                )
    return choices


def source_select_label(
    tenant_name: str,
    tenant_code: str,
    asset_name: str,
    asset_code: str,
    agent_name: str | None,
    agent_code: str,
    source_name: str | None,
    source_code: str,
) -> str:
    agent_label = agent_select_label(
        tenant_name,
        tenant_code,
        asset_name,
        asset_code,
        agent_name,
        agent_code,
    )
    if not source_name or source_name == source_code:
        return f"{agent_label} / {source_code}"
    return f"{agent_label} / {source_name} ({source_code})"


def encode_source_selection(selection: SourceSelection) -> str:
    return json.dumps(
        {
            "tenant_id": selection.tenant_code,
            "asset_id": selection.asset_code,
            "agent_id": selection.agent_code,
            "source_id": selection.source_code,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def decode_source_selection(value: str) -> SourceSelection:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("Source selection must be a JSON object")
    return SourceSelection(
        tenant_code=str(payload["tenant_id"]),
        asset_code=str(payload["asset_id"]),
        agent_code=str(payload["agent_id"]),
        source_code=str(payload["source_id"]),
    )


async def source_select_choices() -> list[tuple[str, str]]:
    state = get_current_state()
    tenants = await ListTenants(state.unit_of_work_factory()).execute()
    choices: list[tuple[str, str]] = []
    for tenant in tenants:
        assets = await ListAssets(state.unit_of_work_factory()).execute(tenant.tenant_code)
        for asset in assets:
            agents = await ListAgents(state.unit_of_work_factory()).execute(
                tenant.tenant_code,
                asset.asset_code,
            )
            for agent in agents:
                sources = await ListSources(state.unit_of_work_factory()).execute(
                    tenant.tenant_code,
                    asset.asset_code,
                    agent.agent_code,
                )
                for source in sources:
                    choices.append(
                        (
                            encode_source_selection(
                                SourceSelection(
                                    tenant_code=tenant.tenant_code,
                                    asset_code=asset.asset_code,
                                    agent_code=agent.agent_code,
                                    source_code=source.source_code,
                                )
                            ),
                            source_select_label(
                                tenant.name,
                                tenant.tenant_code,
                                asset.name,
                                asset.asset_code,
                                agent.name,
                                agent.agent_code,
                                source.name,
                                source.source_code,
                            ),
                        )
                    )
    return choices
