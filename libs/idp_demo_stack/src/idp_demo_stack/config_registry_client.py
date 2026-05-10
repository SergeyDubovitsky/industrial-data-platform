from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from idp_demo_stack.models import ConfigBundle, ConfigRegistryConfig

Output = Callable[[str], None]


def publish_bundle_via_idp_config_registry(
    *,
    config: ConfigRegistryConfig,
    bundle: ConfigBundle,
    output: Output = print,
) -> dict[str, Any]:
    client = ConfigRegistryClient(config)
    _post_create_or_ignore(
        client,
        "/tenants",
        {"tenant_id": bundle.tenant_id, "name": bundle.tenant_id},
    )
    _post_create_or_ignore(
        client,
        _path("tenants", bundle.tenant_id, "assets"),
        {"asset_id": bundle.asset_id, "name": bundle.asset_id},
    )
    _post_create_or_ignore(
        client,
        _path("tenants", bundle.tenant_id, "assets", bundle.asset_id, "agents"),
        {"agent_id": bundle.agent_id},
    )

    source_count = 0
    point_count = 0
    for source in bundle.sources:
        source_count += 1
        _post_create_or_ignore(
            client,
            _path(
                "tenants",
                bundle.tenant_id,
                "assets",
                bundle.asset_id,
                "agents",
                bundle.agent_id,
                "sources",
            ),
            {
                "source_id": source.source_id,
                "source_type": source.source_type,
                "enabled": source.enabled,
                "connection_json": source.connection,
                "acquisition_defaults_json": source.acquisition_defaults,
                "publish_defaults_json": source.publish_defaults,
            },
        )
        for point in source.points:
            point_count += 1
            _post_create_or_ignore(
                client,
                _path(
                    "tenants",
                    bundle.tenant_id,
                    "assets",
                    bundle.asset_id,
                    "agents",
                    bundle.agent_id,
                    "sources",
                    source.source_id,
                    "points",
                ),
                {
                    "point_id": (
                        f"{bundle.tenant_id}|{bundle.asset_id}|"
                        f"{source.source_id}|{point.point_key}"
                    ),
                    "point_key": point.point_key,
                    "point_ref": point.point_ref,
                    "name": point.name,
                    "description": point.description,
                    "value_type": point.value_type,
                    "value_model": point.value_model,
                    "signal_type": point.signal_type,
                    "unit": point.unit,
                    "acquisition_json": point.acquisition,
                    "publish_json": point.publish,
                    "tags_json": point.tags,
                },
            )

    rendered = client.post_json(
        _path(
            "tenants",
            bundle.tenant_id,
            "assets",
            bundle.asset_id,
            "agents",
            bundle.agent_id,
            "render-config",
        ),
        {
            "config_revision": bundle.config_revision,
            "issued_at": bundle.issued_at,
            "source_config_revisions": {
                source.source_id: source.source_config_revision
                for source in bundle.sources
            },
        },
        ignore_conflict=True,
    )
    if rendered.get("status") == "conflict":
        output(
            "CONFIG_REGISTRY_RENDER_SKIPPED_DUPLICATE "
            f"base_url={config.base_url} "
            f"agent_id={bundle.agent_id} "
            f"config_revision={bundle.config_revision}"
        )
        return rendered

    output(
        "CONFIG_REGISTRY_UPSERTED "
        f"base_url={config.base_url} "
        f"tenant_id={bundle.tenant_id} "
        f"asset_id={bundle.asset_id} "
        f"agent_id={bundle.agent_id} "
        f"sources={source_count} "
        f"points={point_count}"
    )
    output(
        "CONFIG_REGISTRY_RENDERED "
        f"base_url={config.base_url} "
        f"agent_id={bundle.agent_id} "
        f"config_revision={bundle.config_revision} "
        f"outbox_records={rendered.get('outbox_record_count')}"
    )
    return rendered


class ConfigRegistryClient:
    def __init__(self, config: ConfigRegistryConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._timeout_seconds = config.timeout_seconds

    def post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        ignore_conflict: bool = False,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            path,
            payload,
            ignore_conflict=ignore_conflict,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        ignore_conflict: bool = False,
    ) -> dict[str, Any]:
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=True).encode()
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            method=method,
        )
        request.add_header("Accept", "application/json")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                response_text = response.read().decode()
        except urllib.error.HTTPError as exc:
            response_text = exc.read().decode(errors="replace")
            if exc.code == 409 and ignore_conflict:
                return {"status": "conflict", "detail": response_text}
            raise RuntimeError(
                "Config Registry request failed: "
                f"method={method} path={path} status={exc.code} body={response_text}"
            ) from exc
        parsed = json.loads(response_text) if response_text else {}
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Config Registry response for {path} must be an object")
        return parsed


def _post_create_or_ignore(
    client: ConfigRegistryClient,
    path: str,
    payload: dict[str, Any],
) -> None:
    client.post_json(path, payload, ignore_conflict=True)


def _path(*segments: str) -> str:
    escaped = [urllib.parse.quote(segment, safe="") for segment in segments]
    return "/" + "/".join(escaped)
