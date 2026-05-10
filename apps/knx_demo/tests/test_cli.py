from __future__ import annotations

import pytest

from knx_demo import cli


def test_main_routes_read_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[str] | None] = []

    def fake_main(argv: list[str] | None = None) -> None:
        captured.append(argv)

    monkeypatch.setattr(cli.read_signals, "main", fake_main)

    cli.main(["read-signals", "--address", "0/0/7"])

    assert captured == [["--address", "0/0/7"]]


def test_main_routes_blink_melody(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[str] | None] = []

    def fake_main(argv: list[str] | None = None) -> None:
        captured.append(argv)

    monkeypatch.setattr(cli.blink_melody, "main", fake_main)

    cli.main(["blink-melody", "--switch-address", "0/0/1"])

    assert captured == [["--switch-address", "0/0/1"]]


def test_main_requires_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="2"):
        cli.main([])

    captured = capsys.readouterr()
    assert "usage:" in captured.err
