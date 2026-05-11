from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse

from idp_synthetic_config.models import JsonObject, SyntheticModel

LOCAL_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "idp-config-registry",
    "postgres",
    "clickhouse",
    "mqtt-broker",
    "redpanda-connect",
    "host.docker.internal",
}


class DestructiveResetRefused(RuntimeError):
    """Raised when reset would target a non-local endpoint without opt-in."""


@dataclass(frozen=True)
class ResetTargetSummary:
    name: str
    status: str
    records_affected: int
    detail: str

    def to_dict(self) -> JsonObject:
        return {
            "name": self.name,
            "status": self.status,
            "records_affected": self.records_affected,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ResetSummary:
    enabled: bool
    target_kind: str
    warning: str | None
    targets: tuple[ResetTargetSummary, ...]

    def with_target(self, target: ResetTargetSummary) -> ResetSummary:
        return ResetSummary(
            enabled=self.enabled,
            target_kind=self.target_kind,
            warning=self.warning,
            targets=tuple(
                target if existing.name == target.name else existing
                for existing in self.targets
            ),
        )

    def to_dict(self) -> JsonObject:
        return {
            "enabled": self.enabled,
            "target_kind": self.target_kind,
            "warning": self.warning,
            "targets": [target.to_dict() for target in self.targets],
        }


@dataclass(frozen=True)
class ResetPolicy:
    enabled: bool = True
    allow_destructive_reset: bool = False
    clickhouse_url: str | None = None
    mqtt_broker_url: str | None = None

    def evaluate(
        self,
        model: SyntheticModel,
        *,
        config_registry_url: str,
    ) -> ResetSummary:
        if not self.enabled:
            return ResetSummary(
                enabled=False,
                target_kind="disabled",
                warning=None,
                targets=(),
            )

        target_kind = "local" if is_local_endpoint(config_registry_url) else "non-local"
        if target_kind == "non-local" and not self.allow_destructive_reset:
            raise DestructiveResetRefused(
                "Refusing destructive reset for non-local Config Registry target. "
                "Use --no-reset or pass --allow-destructive-reset explicitly."
            )

        warning = None
        if target_kind == "non-local":
            warning = (
                "Destructive reset for non-local target was explicitly enabled "
                "with --allow-destructive-reset."
            )

        points = sum(len(source.points) for source in model.sources)
        targets = (
            ResetTargetSummary(
                name="config_registry",
                status="planned",
                records_affected=0,
                detail=(
                    "Seeder will delete the existing generated Config Registry "
                    "agent graph before recreating "
                    f"{points} desired points."
                ),
            ),
            ResetTargetSummary(
                name="clickhouse",
                status="unsupported" if self.clickhouse_url else "skipped",
                records_affected=0,
                detail=(
                    "ClickHouse reset is not implemented yet; configured URL "
                    f"{self.clickhouse_url} was not used."
                    if self.clickhouse_url
                    else "ClickHouse reset URL was not configured."
                ),
            ),
            ResetTargetSummary(
                name="mqtt_retained_config",
                status="unsupported" if self.mqtt_broker_url else "skipped",
                records_affected=0,
                detail=(
                    "MQTT retained config reset is not implemented yet; configured "
                    f"broker URL {self.mqtt_broker_url} was not used."
                    if self.mqtt_broker_url
                    else "MQTT retained reset endpoint was not configured."
                ),
            ),
        )
        return ResetSummary(
            enabled=True,
            target_kind=target_kind,
            warning=warning,
            targets=targets,
        )


def is_local_endpoint(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    hostname = parsed.hostname
    if hostname is None:
        return False
    hostname = hostname.lower()
    if hostname in LOCAL_HOSTS:
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False
