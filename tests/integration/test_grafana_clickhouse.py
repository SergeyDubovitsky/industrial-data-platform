from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.integration_grafana,
    pytest.mark.integration_web_monitoring,
]
REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_FILE = (
    REPO_ROOT / "infra" / "local" / "grafana" / "dashboards" / "telemetry-overview.json"
)
DATASOURCE_UID = "idp-telemetry-store-telemetry-store"
DASHBOARD_UID = "idp-telemetry-overview"
RUN_ID = "grafana-it"


@pytest.mark.integration_smoke
def test_grafana_reads_clickhouse_telemetry_read_models(
    local_grafana_clickhouse_stack,
) -> None:
    load_poc_result = subprocess.run(
        [
            "uv",
            "run",
            "--env-file",
            str(local_grafana_clickhouse_stack.env_file),
            "idp-telemetry-store",
            "load-poc",
            "telemetry-read-models",
            "--rows",
            "2000",
            "--points",
            "20",
            "--batch-size",
            "1000",
            "--duplicate-every",
            "10",
            "--run-id",
            RUN_ID,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert load_poc_result.returncode == 0, load_poc_result.stderr

    datasource = local_grafana_clickhouse_stack.grafana_json(
        "GET",
        f"/api/datasources/uid/{DATASOURCE_UID}",
    )
    assert isinstance(datasource, dict)
    assert datasource["uid"] == DATASOURCE_UID
    assert datasource["type"] == "grafana-clickhouse-datasource"

    search_results = _wait_for_dashboard_search_results(
        local_grafana_clickhouse_stack,
        query="Telemetry%20Overview",
        dashboard_uid=DASHBOARD_UID,
    )
    assert any(item.get("uid") == DASHBOARD_UID for item in search_results)

    dashboard_response = local_grafana_clickhouse_stack.grafana_json(
        "GET",
        f"/api/dashboards/uid/{DASHBOARD_UID}",
    )
    assert isinstance(dashboard_response, dict)
    dashboard = dashboard_response["dashboard"]
    assert isinstance(dashboard, dict)
    assert dashboard["uid"] == DASHBOARD_UID

    dashboard_json = DASHBOARD_FILE.read_text(encoding="utf-8")
    assert DATASOURCE_UID in dashboard_json
    assert "telemetry_latest_v1" in dashboard_json
    assert "telemetry_1m_v1" in dashboard_json
    assert "telemetry_1h_v1" in dashboard_json
    assert "meta/catalog" not in dashboard_json
    assert "idp/v1/" not in dashboard_json

    query_response = local_grafana_clickhouse_stack.grafana_json(
        "POST",
        "/api/ds/query",
        _grafana_table_query_payload(
            f"""
            SELECT count() AS latest_points
            FROM telemetry_latest_v1
            WHERE tenant_id = 'poc-tenant-{RUN_ID}'
            """.strip()
        ),
        timeout=60,
    )
    assert isinstance(query_response, dict)
    assert _contains_scalar_value(query_response, 20), json.dumps(
        query_response,
        indent=2,
        sort_keys=True,
    )


def _grafana_table_query_payload(raw_sql: str) -> dict[str, object]:
    now_ms = int(time.time() * 1000)
    return {
        "from": str(now_ms - 6 * 60 * 60 * 1000),
        "to": str(now_ms),
        "queries": [
            {
                "datasource": {
                    "type": "grafana-clickhouse-datasource",
                    "uid": DATASOURCE_UID,
                },
                "editorType": "sql",
                "format": 1,
                "intervalMs": 60000,
                "maxDataPoints": 500,
                "meta": {
                    "builderOptions": {
                        "columns": [],
                        "database": "",
                        "limit": 1000,
                        "mode": "list",
                        "queryType": "table",
                        "table": "",
                    }
                },
                "pluginVersion": "4.15.0",
                "queryType": "table",
                "rawSql": raw_sql,
                "refId": "A",
            }
        ],
        "range": {
            "from": "now-6h",
            "to": "now",
            "raw": {
                "from": "now-6h",
                "to": "now",
            },
        },
    }


def _contains_scalar_value(value: Any, expected: object) -> bool:
    if value == expected:
        return True
    if isinstance(value, dict):
        return any(_contains_scalar_value(item, expected) for item in value.values())
    if isinstance(value, list):
        return any(_contains_scalar_value(item, expected) for item in value)
    return False


def _wait_for_dashboard_search_results(
    local_grafana_clickhouse_stack,
    *,
    query: str,
    dashboard_uid: str,
    timeout: float = 30.0,
) -> list[dict[str, object]]:
    deadline = time.monotonic() + timeout
    last_results: list[dict[str, object]] = []

    while time.monotonic() < deadline:
        search_results = local_grafana_clickhouse_stack.grafana_json(
            "GET",
            f"/api/search?query={query}",
        )
        assert isinstance(search_results, list)

        normalized_results = [
            item for item in search_results if isinstance(item, dict)
        ]
        if any(item.get("uid") == dashboard_uid for item in normalized_results):
            return normalized_results

        last_results = normalized_results
        time.sleep(1)

    raise AssertionError(
        f"Grafana dashboard {dashboard_uid!r} did not appear in search within "
        f"{timeout:.0f}s. Last search results: {json.dumps(last_results, sort_keys=True)}"
    )
