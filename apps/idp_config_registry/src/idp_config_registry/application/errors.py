from __future__ import annotations


class ApplicationError(RuntimeError):
    """Base class for platform configuration application errors."""


class DuplicateTenantError(ApplicationError):
    def __init__(self, tenant_id: str) -> None:
        super().__init__(f"Tenant {tenant_id!r} already exists")
        self.tenant_id = tenant_id


class TenantNotFoundError(ApplicationError):
    def __init__(self, tenant_id: str) -> None:
        super().__init__(f"Tenant {tenant_id!r} does not exist")
        self.tenant_id = tenant_id


class TenantHasAssetsError(ApplicationError):
    def __init__(self, tenant_id: str) -> None:
        super().__init__(f"Tenant {tenant_id!r} cannot be deleted while it still has assets")
        self.tenant_id = tenant_id


class DuplicateAssetError(ApplicationError):
    def __init__(self, tenant_id: str, asset_id: str) -> None:
        super().__init__(f"Asset {asset_id!r} already exists for tenant {tenant_id!r}")
        self.tenant_id = tenant_id
        self.asset_id = asset_id


class AssetNotFoundError(ApplicationError):
    def __init__(self, tenant_id: str, asset_id: str) -> None:
        super().__init__(f"Asset {asset_id!r} does not exist for tenant {tenant_id!r}")
        self.tenant_id = tenant_id
        self.asset_id = asset_id


class AssetHasAgentsError(ApplicationError):
    def __init__(self, tenant_id: str, asset_id: str) -> None:
        super().__init__(
            f"Asset {asset_id!r} cannot be deleted while it still has agents "
            f"in tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id


class DuplicateAgentError(ApplicationError):
    def __init__(self, tenant_id: str, asset_id: str, agent_id: str) -> None:
        super().__init__(
            f"Agent {agent_id!r} already exists for asset {asset_id!r} "
            f"in tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id


class AgentNotFoundError(ApplicationError):
    def __init__(self, tenant_id: str, asset_id: str, agent_id: str) -> None:
        super().__init__(
            f"Agent {agent_id!r} does not exist for asset {asset_id!r} "
            f"in tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id


class AgentHasChildrenError(ApplicationError):
    def __init__(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        *,
        reason: str,
    ) -> None:
        super().__init__(
            f"Agent {agent_id!r} cannot be deleted for asset {asset_id!r} "
            f"in tenant {tenant_id!r}: {reason}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id
        self.reason = reason


class DuplicateSourceError(ApplicationError):
    def __init__(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> None:
        super().__init__(
            f"Source {source_id!r} already exists for agent {agent_id!r} "
            f"in asset {asset_id!r} and tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id
        self.source_id = source_id


class SourceNotFoundError(ApplicationError):
    def __init__(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
    ) -> None:
        super().__init__(
            f"Source {source_id!r} does not exist for agent {agent_id!r} "
            f"in asset {asset_id!r} and tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id
        self.source_id = source_id


class SourceHasChildrenError(ApplicationError):
    def __init__(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        *,
        reason: str,
    ) -> None:
        super().__init__(
            f"Source {source_id!r} cannot be deleted for agent {agent_id!r} "
            f"in asset {asset_id!r} and tenant {tenant_id!r}: {reason}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id
        self.source_id = source_id
        self.reason = reason


class DuplicatePointError(ApplicationError):
    def __init__(self, tenant_id: str, field_name: str, field_value: str) -> None:
        super().__init__(
            f"Point with {field_name} {field_value!r} already exists "
            f"for tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.field_name = field_name
        self.field_value = field_value


class PointNotFoundError(ApplicationError):
    def __init__(self, tenant_id: str, point_id: str) -> None:
        super().__init__(
            f"Point {point_id!r} does not exist for tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.point_id = point_id


class ConfigRenderError(ApplicationError):
    """Raised when registry state cannot be rendered to edge config contracts."""


class ConfigPayloadValidationError(ConfigRenderError):
    def __init__(self, message_type: str, errors: list[str]) -> None:
        message = f"{message_type} payload violates contract: " + "; ".join(errors)
        super().__init__(message)
        self.message_type = message_type
        self.errors = errors


class DuplicateConfigRevisionError(ApplicationError):
    def __init__(self, tenant_id: str, asset_id: str, agent_id: str, revision: str) -> None:
        super().__init__(
            f"Config revision {revision!r} already exists for agent {agent_id!r} "
            f"in asset {asset_id!r} and tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id
        self.revision = revision


class DuplicateSourceConfigRevisionError(ApplicationError):
    def __init__(
        self,
        tenant_id: str,
        asset_id: str,
        agent_id: str,
        source_id: str,
        revision: str,
    ) -> None:
        super().__init__(
            f"Source config revision {revision!r} already exists for source "
            f"{source_id!r} in agent {agent_id!r}, asset {asset_id!r}, "
            f"tenant {tenant_id!r}"
        )
        self.tenant_id = tenant_id
        self.asset_id = asset_id
        self.agent_id = agent_id
        self.source_id = source_id
        self.revision = revision


class DuplicateConfigOutboxRecordError(ApplicationError):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Config outbox record with idempotency key {idempotency_key!r} already exists"
        )
        self.idempotency_key = idempotency_key
