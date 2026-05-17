from __future__ import annotations

from fastapi.testclient import TestClient

from idp_config_registry.main import create_app


def test_health_and_ready_endpoints() -> None:
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_openapi_keeps_public_id_path_parameter_names() -> None:
    client = TestClient(create_app())

    openapi = client.get("/openapi.json").json()
    agent_create_params = openapi["paths"][
        "/tenants/{tenant_id}/assets/{asset_id}/agents"
    ]["post"]["parameters"]
    point_delete_params = openapi["paths"][
        "/tenants/{tenant_id}/assets/{asset_id}/agents/{agent_id}"
        "/sources/{source_id}/points/{point_id}"
    ]["delete"]["parameters"]

    assert [param["name"] for param in agent_create_params] == [
        "tenant_id",
        "asset_id",
    ]
    assert [param["name"] for param in point_delete_params] == [
        "tenant_id",
        "asset_id",
        "agent_id",
        "source_id",
        "point_id",
    ]


def test_create_and_list_tenants() -> None:
    client = TestClient(create_app())

    create_response = client.post(
        "/tenants",
        json={"tenant_id": "tenant-a", "name": "Tenant A"},
    )
    list_response = client.get("/tenants")

    assert create_response.status_code == 201
    assert create_response.json()["tenant_id"] == "tenant-a"
    assert list_response.status_code == 200
    assert [tenant["tenant_id"] for tenant in list_response.json()] == ["tenant-a"]


def test_create_and_list_assets() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})

    create_response = client.post(
        "/tenants/tenant-a/assets",
        json={
            "asset_id": "asset-a",
            "name": "Asset A",
            "description": "Primary monitored asset",
        },
    )
    list_response = client.get("/tenants/tenant-a/assets")

    assert create_response.status_code == 201
    assert create_response.json()["asset_id"] == "asset-a"
    assert create_response.json()["description"] == "Primary monitored asset"
    assert list_response.status_code == 200
    assert [asset["asset_id"] for asset in list_response.json()] == ["asset-a"]


def test_create_asset_rejects_missing_tenant() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )

    assert response.status_code == 404


def test_create_asset_rejects_duplicate_id() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})

    first_response = client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    second_response = client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_create_and_list_agents() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )

    create_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={
            "agent_id": "agent-a",
            "name": "Agent A",
            "bootstrap_hint_json": {"mqtt_profile": "local"},
        },
    )
    list_response = client.get("/tenants/tenant-a/assets/asset-a/agents")

    assert create_response.status_code == 201
    assert create_response.json()["agent_id"] == "agent-a"
    assert create_response.json()["bootstrap_hint_json"] == {"mqtt_profile": "local"}
    assert list_response.status_code == 200
    assert [agent["agent_id"] for agent in list_response.json()] == ["agent-a"]


def test_create_agent_rejects_missing_asset() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )

    assert response.status_code == 404


def test_create_agent_rejects_duplicate_id() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )

    first_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )
    second_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_create_and_list_sources() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )

    create_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={
            "source_id": "knx-main",
            "source_type": "knx",
            "name": "Main KNX Line",
            "connection_json": {"gateway": "127.0.0.1"},
        },
    )
    list_response = client.get(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources"
    )

    assert create_response.status_code == 201
    assert create_response.json()["source_id"] == "knx-main"
    assert create_response.json()["connection_json"] == {"gateway": "127.0.0.1"}
    assert list_response.status_code == 200
    assert [source["source_id"] for source in list_response.json()] == ["knx-main"]


def test_create_source_rejects_missing_agent() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={"source_id": "knx-main", "source_type": "knx"},
    )

    assert response.status_code == 404


def test_create_source_rejects_duplicate_id() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )

    first_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={"source_id": "knx-main", "source_type": "knx"},
    )
    second_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={"source_id": "knx-main", "source_type": "knx"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_create_and_list_points() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={"source_id": "knx-main", "source_type": "knx"},
    )

    create_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources/knx-main/points",
        json={
            "point_id": "tenant-a|asset-a|knx-main|lights.main",
            "point_key": "lights.main",
            "point_ref": "1/1/1",
            "name": "Main Light",
            "value_type": "boolean",
            "value_model": "1.001",
            "signal_type": "feedback",
            "tags_json": {"room": "hall"},
        },
    )
    list_response = client.get(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points"
    )

    assert create_response.status_code == 201
    assert create_response.json()["point_key"] == "lights.main"
    assert create_response.json()["tags_json"] == {"room": "hall"}
    assert list_response.status_code == 200
    assert [point["point_key"] for point in list_response.json()] == ["lights.main"]


def test_delete_point_removes_existing_point() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={"source_id": "knx-main", "source_type": "knx"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources/knx-main/points",
        json={
            "point_id": "tenant-a|asset-a|knx-main|lights.main",
            "point_key": "lights.main",
            "point_ref": "1/1/1",
            "name": "Main Light",
            "value_type": "boolean",
            "value_model": "1.001",
            "signal_type": "feedback",
        },
    )

    delete_response = client.delete(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points/tenant-a%7Casset-a%7Cknx-main%7Clights.main"
    )
    list_response = client.get(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points"
    )

    assert delete_response.status_code == 204
    assert list_response.json() == []


def test_delete_point_rejects_point_id_outside_url_scope() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    for asset_code, agent_code, source_code in (
        ("asset-a", "agent-a", "knx-main"),
        ("asset-b", "agent-b", "knx-secondary"),
    ):
        client.post(
            "/tenants/tenant-a/assets",
            json={"asset_id": asset_code, "name": asset_code},
        )
        client.post(
            f"/tenants/tenant-a/assets/{asset_code}/agents",
            json={"agent_id": agent_code},
        )
        client.post(
            f"/tenants/tenant-a/assets/{asset_code}/agents/{agent_code}/sources",
            json={"source_id": source_code, "source_type": "knx"},
        )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources/knx-main/points",
        json={
            "point_id": "shared-point",
            "point_key": "lights.main",
            "point_ref": "1/1/1",
            "name": "Main Light",
            "value_type": "boolean",
            "value_model": "1.001",
            "signal_type": "feedback",
        },
    )

    delete_response = client.delete(
        "/tenants/tenant-a/assets/asset-b/agents/agent-b"
        "/sources/knx-secondary/points/shared-point"
    )
    list_response = client.get(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points"
    )

    assert delete_response.status_code == 404
    assert [point["point_id"] for point in list_response.json()] == ["shared-point"]


def test_delete_agent_registry_graph_removes_rendered_slice() -> None:
    client = TestClient(create_app())
    _create_renderable_graph(client)
    render_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/render-config",
        json={
            "config_revision": "rev-api-reset-001",
            "issued_at": "2026-05-03T10:00:00Z",
            "source_config_revisions": {"knx-main": "rev-api-reset-001-knx-main"},
        },
    )

    delete_response = client.delete(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/registry-graph"
        "?delete_empty_asset=true&delete_empty_tenant=true"
    )
    tenants_response = client.get("/tenants")

    assert render_response.status_code == 201
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "tenant_id": "tenant-a",
        "asset_id": "asset-a",
        "agent_id": "agent-a",
        "config_outbox_records_deleted": 2,
        "source_config_revisions_deleted": 1,
        "agent_runtime_config_revisions_deleted": 1,
        "points_deleted": 1,
        "sources_deleted": 1,
        "agents_deleted": 1,
        "assets_deleted": 1,
        "tenants_deleted": 1,
    }
    assert tenants_response.json() == []


def test_delete_agent_registry_graph_is_idempotent_for_missing_slice() -> None:
    client = TestClient(create_app())

    response = client.delete(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/registry-graph"
        "?delete_empty_asset=true&delete_empty_tenant=true"
    )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant-a",
        "asset_id": "asset-a",
        "agent_id": "agent-a",
        "config_outbox_records_deleted": 0,
        "source_config_revisions_deleted": 0,
        "agent_runtime_config_revisions_deleted": 0,
        "points_deleted": 0,
        "sources_deleted": 0,
        "agents_deleted": 0,
        "assets_deleted": 0,
        "tenants_deleted": 0,
    }


def test_render_config_endpoint_stores_revision_and_outbox_records() -> None:
    client = TestClient(create_app())
    _create_renderable_graph(client)

    response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/render-config",
        json={
            "config_revision": "rev-api-001",
            "issued_at": "2026-05-03T10:00:00Z",
            "source_config_revisions": {"knx-main": "rev-api-001-knx-main"},
        },
    )
    duplicate_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/render-config",
        json={
            "config_revision": "rev-api-001",
            "issued_at": "2026-05-03T10:00:00Z",
            "source_config_revisions": {"knx-main": "rev-api-001-knx-main"},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["tenant_id"] == "tenant-a"
    assert payload["config_revision"] == "rev-api-001"
    assert payload["agent_runtime_payload"]["message_type"] == "idp.edge.agent-runtime-config.v1"
    assert payload["source_payloads"][0]["source_id"] == "knx-main"
    assert payload["outbox_record_count"] == 2
    assert duplicate_response.status_code == 409


def test_create_point_rejects_missing_source() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources/knx-main/points",
        json={
            "point_id": "tenant-a|asset-a|knx-main|lights.main",
            "point_key": "lights.main",
            "point_ref": "1/1/1",
            "name": "Main Light",
            "value_type": "boolean",
            "value_model": "1.001",
            "signal_type": "feedback",
        },
    )

    assert response.status_code == 404


def test_create_point_rejects_duplicate_point_id() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={"source_id": "knx-main", "source_type": "knx"},
    )
    payload = {
        "point_id": "tenant-a|asset-a|knx-main|lights.main",
        "point_key": "lights.main",
        "point_ref": "1/1/1",
        "name": "Main Light",
        "value_type": "boolean",
        "value_model": "1.001",
        "signal_type": "feedback",
    }

    first_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources/knx-main/points",
        json=payload,
    )
    second_response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources/knx-main/points",
        json={**payload, "point_key": "lights.secondary", "point_ref": "1/1/2"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_create_agent_rejects_domain_invalid_payload() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )

    response = client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "Agent A"},
    )

    assert response.status_code == 422


def test_list_agents_rejects_missing_asset() -> None:
    client = TestClient(create_app())

    response = client.get("/tenants/tenant-a/assets/asset-a/agents")

    assert response.status_code == 404


def test_create_asset_rejects_domain_invalid_payload() -> None:
    client = TestClient(create_app())
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})

    response = client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "Asset A", "name": "Asset A"},
    )

    assert response.status_code == 422


def test_list_assets_rejects_missing_tenant() -> None:
    client = TestClient(create_app())

    response = client.get("/tenants/tenant-a/assets")

    assert response.status_code == 404


def test_create_tenant_rejects_duplicate_id() -> None:
    client = TestClient(create_app())

    first_response = client.post(
        "/tenants",
        json={"tenant_id": "tenant-a", "name": "Tenant A"},
    )
    second_response = client.post(
        "/tenants",
        json={"tenant_id": "tenant-a", "name": "Tenant A"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_create_tenant_rejects_domain_invalid_payload() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/tenants",
        json={"tenant_id": "tenant-a", "name": " "},
    )

    assert response.status_code == 422


def _create_renderable_graph(client: TestClient) -> None:
    client.post("/tenants", json={"tenant_id": "tenant-a", "name": "Tenant A"})
    client.post(
        "/tenants/tenant-a/assets",
        json={"asset_id": "asset-a", "name": "Asset A"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents",
        json={"agent_id": "agent-a"},
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a/sources",
        json={
            "source_id": "knx-main",
            "source_type": "knx",
            "connection_json": {"gateway_ip": "127.0.0.1"},
            "acquisition_defaults_json": {
                "listen": True,
                "read_on_start": False,
                "periodic_interval_seconds": None,
            },
            "publish_defaults_json": {
                "enabled": True,
                "change_threshold": None,
            },
        },
    )
    client.post(
        "/tenants/tenant-a/assets/asset-a/agents/agent-a"
        "/sources/knx-main/points",
        json={
            "point_id": "tenant-a|asset-a|knx-main|temperature",
            "point_key": "temperature",
            "point_ref": "2/0/0",
            "name": "Temperature",
            "value_type": "number",
            "value_model": "knx.dpt.9.001",
            "signal_type": "sensor",
            "acquisition_json": {"read_on_start": True},
            "publish_json": {"change_threshold": 1.0},
            "tags_json": {"room": "demo"},
        },
    )
