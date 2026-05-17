from __future__ import annotations


class ApplicationError(RuntimeError):
    """Base class for platform configuration application errors."""


class DuplicateTenantError(ApplicationError):
    def __init__(self, tenant_code: str) -> None:
        super().__init__(f"Tenant {tenant_code!r} already exists")
        self.tenant_code = tenant_code


class TenantNotFoundError(ApplicationError):
    def __init__(self, tenant_code: str) -> None:
        super().__init__(f"Tenant {tenant_code!r} does not exist")
        self.tenant_code = tenant_code


class TenantHasAssetsError(ApplicationError):
    def __init__(self, tenant_code: str) -> None:
        super().__init__(f"Tenant {tenant_code!r} cannot be deleted while it still has assets")
        self.tenant_code = tenant_code


class DuplicateAssetError(ApplicationError):
    def __init__(self, tenant_code: str, asset_code: str) -> None:
        super().__init__(f"Asset {asset_code!r} already exists for tenant {tenant_code!r}")
        self.tenant_code = tenant_code
        self.asset_code = asset_code


class AssetNotFoundError(ApplicationError):
    def __init__(self, tenant_code: str, asset_code: str) -> None:
        super().__init__(f"Asset {asset_code!r} does not exist for tenant {tenant_code!r}")
        self.tenant_code = tenant_code
        self.asset_code = asset_code


class AssetHasAgentsError(ApplicationError):
    def __init__(self, tenant_code: str, asset_code: str) -> None:
        super().__init__(
            f"Asset {asset_code!r} cannot be deleted while it still has agents "
            f"in tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code


class DuplicateAgentError(ApplicationError):
    def __init__(self, tenant_code: str, asset_code: str, agent_code: str) -> None:
        super().__init__(
            f"Agent {agent_code!r} already exists for asset {asset_code!r} "
            f"in tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code


class AgentNotFoundError(ApplicationError):
    def __init__(self, tenant_code: str, asset_code: str, agent_code: str) -> None:
        super().__init__(
            f"Agent {agent_code!r} does not exist for asset {asset_code!r} "
            f"in tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code


class AgentHasChildrenError(ApplicationError):
    def __init__(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        *,
        reason: str,
    ) -> None:
        super().__init__(
            f"Agent {agent_code!r} cannot be deleted for asset {asset_code!r} "
            f"in tenant {tenant_code!r}: {reason}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code
        self.reason = reason


class DuplicateSourceError(ApplicationError):
    def __init__(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> None:
        super().__init__(
            f"Source {source_code!r} already exists for agent {agent_code!r} "
            f"in asset {asset_code!r} and tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code
        self.source_code = source_code


class SourceNotFoundError(ApplicationError):
    def __init__(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
    ) -> None:
        super().__init__(
            f"Source {source_code!r} does not exist for agent {agent_code!r} "
            f"in asset {asset_code!r} and tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code
        self.source_code = source_code


class SourceHasChildrenError(ApplicationError):
    def __init__(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
        *,
        reason: str,
    ) -> None:
        super().__init__(
            f"Source {source_code!r} cannot be deleted for agent {agent_code!r} "
            f"in asset {asset_code!r} and tenant {tenant_code!r}: {reason}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code
        self.source_code = source_code
        self.reason = reason


class DuplicatePointError(ApplicationError):
    def __init__(self, tenant_code: str, field_name: str, field_value: str) -> None:
        super().__init__(
            f"Point with {field_name} {field_value!r} already exists "
            f"for tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.field_name = field_name
        self.field_value = field_value


class PointNotFoundError(ApplicationError):
    def __init__(self, tenant_code: str, point_code: str) -> None:
        super().__init__(
            f"Point {point_code!r} does not exist for tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.point_code = point_code


class ConfigRenderError(ApplicationError):
    """Raised when registry state cannot be rendered to edge config contracts."""


class ConfigPayloadValidationError(ConfigRenderError):
    def __init__(self, message_type: str, errors: list[str]) -> None:
        message = f"{message_type} payload violates contract: " + "; ".join(errors)
        super().__init__(message)
        self.message_type = message_type
        self.errors = errors


class DuplicateConfigRevisionError(ApplicationError):
    def __init__(self, tenant_code: str, asset_code: str, agent_code: str, revision: str) -> None:
        super().__init__(
            f"Config revision {revision!r} already exists for agent {agent_code!r} "
            f"in asset {asset_code!r} and tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code
        self.revision = revision


class DuplicateSourceConfigRevisionError(ApplicationError):
    def __init__(
        self,
        tenant_code: str,
        asset_code: str,
        agent_code: str,
        source_code: str,
        revision: str,
    ) -> None:
        super().__init__(
            f"Source config revision {revision!r} already exists for source "
            f"{source_code!r} in agent {agent_code!r}, asset {asset_code!r}, "
            f"tenant {tenant_code!r}"
        )
        self.tenant_code = tenant_code
        self.asset_code = asset_code
        self.agent_code = agent_code
        self.source_code = source_code
        self.revision = revision


class DuplicateConfigOutboxRecordError(ApplicationError):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Config outbox record with idempotency key {idempotency_key!r} already exists"
        )
        self.idempotency_key = idempotency_key
