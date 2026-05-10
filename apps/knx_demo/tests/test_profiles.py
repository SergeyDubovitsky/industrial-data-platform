import pytest

from knx_demo.domain.profiles import EndpointProfile, resolve_endpoint_profile


def test_resolve_endpoint_profile_uses_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KNX_EXTERNAL_GATEWAY_IP", raising=False)
    monkeypatch.delenv("KNX_EXTERNAL_GATEWAY_PORT", raising=False)
    monkeypatch.delenv("KNX_EXTERNAL_ROUTE_BACK", raising=False)

    profile = resolve_endpoint_profile("external")

    assert profile == EndpointProfile(
        gateway_ip="203.0.113.234",
        gateway_port=7171,
        route_back=True,
    )


def test_resolve_endpoint_profile_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KNX_EXTERNAL_GATEWAY_IP", "198.51.100.25")
    monkeypatch.setenv("KNX_EXTERNAL_GATEWAY_PORT", "4671")
    monkeypatch.setenv("KNX_EXTERNAL_ROUTE_BACK", "false")

    profile = resolve_endpoint_profile("external")

    assert profile == EndpointProfile(
        gateway_ip="198.51.100.25",
        gateway_port=4671,
        route_back=False,
    )


def test_resolve_endpoint_profile_applies_overrides() -> None:
    profile = resolve_endpoint_profile(
        "local",
        gateway_ip="10.0.0.5",
        gateway_port=4000,
        route_back=True,
    )

    assert profile == EndpointProfile(
        gateway_ip="10.0.0.5",
        gateway_port=4000,
        route_back=True,
    )
