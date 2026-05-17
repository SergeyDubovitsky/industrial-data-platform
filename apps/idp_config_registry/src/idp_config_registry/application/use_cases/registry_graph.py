from __future__ import annotations

from dataclasses import dataclass

from idp_config_registry.application.ports.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class DeleteAgentRegistryGraphCommand:
    tenant_code: str
    asset_code: str
    agent_code: str
    delete_empty_asset: bool = False
    delete_empty_tenant: bool = False


@dataclass(frozen=True)
class DeleteAgentRegistryGraphResult:
    tenant_code: str
    asset_code: str
    agent_code: str
    config_outbox_records_deleted: int
    source_config_revisions_deleted: int
    agent_runtime_config_revisions_deleted: int
    points_deleted: int
    sources_deleted: int
    agents_deleted: int
    assets_deleted: int
    tenants_deleted: int

    @property
    def records_deleted(self) -> int:
        return (
            self.config_outbox_records_deleted
            + self.source_config_revisions_deleted
            + self.agent_runtime_config_revisions_deleted
            + self.points_deleted
            + self.sources_deleted
            + self.agents_deleted
            + self.assets_deleted
            + self.tenants_deleted
        )


class DeleteAgentRegistryGraph:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        command: DeleteAgentRegistryGraphCommand,
    ) -> DeleteAgentRegistryGraphResult:
        async with self._unit_of_work as unit_of_work:
            tenant = await unit_of_work.tenants.get(command.tenant_code)
            asset = await unit_of_work.assets.get(command.tenant_code, command.asset_code)
            agent = await unit_of_work.agents.get(
                command.tenant_code,
                command.asset_code,
                command.agent_code,
            )

            config_outbox_records_deleted = (
                await unit_of_work.config_outbox.delete_for_agent(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                )
            )
            source_config_revisions_deleted = 0
            agent_runtime_config_revisions_deleted = 0
            points_deleted = 0
            sources_deleted = 0
            agents_deleted = 0
            assets_deleted = 0
            tenants_deleted = 0

            if agent is not None:
                source_config_revisions_deleted = (
                    await unit_of_work.source_config_revisions.delete_for_agent(
                        command.tenant_code,
                        command.asset_code,
                        command.agent_code,
                    )
                )
                agent_runtime_config_revisions_deleted = (
                    await unit_of_work.agent_runtime_config_revisions.delete_for_agent(
                        command.tenant_code,
                        command.asset_code,
                        command.agent_code,
                    )
                )
                points_deleted = await unit_of_work.points.delete_for_agent(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                )
                sources_deleted = await unit_of_work.sources.delete_for_agent(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                )
                await unit_of_work.agents.delete(
                    command.tenant_code,
                    command.asset_code,
                    command.agent_code,
                )
                agents_deleted = 1

            if command.delete_empty_asset and asset is not None:
                remaining_agents = await unit_of_work.agents.list_for_asset(
                    command.tenant_code,
                    command.asset_code,
                )
                if not remaining_agents:
                    await unit_of_work.assets.delete(command.tenant_code, command.asset_code)
                    assets_deleted = 1

            if command.delete_empty_tenant and tenant is not None:
                remaining_assets = await unit_of_work.assets.list_for_tenant(
                    command.tenant_code
                )
                if not remaining_assets:
                    await unit_of_work.tenants.delete(command.tenant_code)
                    tenants_deleted = 1

            await unit_of_work.commit()

        return DeleteAgentRegistryGraphResult(
            tenant_code=command.tenant_code,
            asset_code=command.asset_code,
            agent_code=command.agent_code,
            config_outbox_records_deleted=config_outbox_records_deleted,
            source_config_revisions_deleted=source_config_revisions_deleted,
            agent_runtime_config_revisions_deleted=agent_runtime_config_revisions_deleted,
            points_deleted=points_deleted,
            sources_deleted=sources_deleted,
            agents_deleted=agents_deleted,
            assets_deleted=assets_deleted,
            tenants_deleted=tenants_deleted,
        )
