from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Sequence
from typing import Any

from xknx import XKNX
from xknx.core import ValueReader
from xknx.devices import BinarySensor, Switch
from xknx.io import ConnectionConfig, ConnectionType
from xknx.remote_value import RemoteValueRaw
from xknx.telegram import GroupAddress, Telegram

from knx_demo.domain.profiles import EndpointProfile
from knx_demo.domain.telemetry import (
    FeedbackSnapshot,
    ReadResult,
    SignalUpdate,
    TelegramEvent,
)


def _connection_config(profile: EndpointProfile) -> ConnectionConfig:
    return ConnectionConfig(
        connection_type=ConnectionType.TUNNELING,
        gateway_ip=profile.gateway_ip,
        gateway_port=profile.gateway_port,
        route_back=profile.route_back,
        auto_reconnect=False,
    )


def _schedule(result: object) -> None:
    if inspect.isawaitable(result):
        asyncio.create_task(result)


def _telegram_event(telegram: Telegram) -> TelegramEvent:
    source_address = getattr(telegram, "source_address", None)
    destination_address = getattr(telegram, "destination_address", None)
    payload = getattr(telegram, "payload", None)
    return TelegramEvent(
        rendered=str(telegram),
        source_address=str(source_address) if source_address is not None else None,
        destination_address=(
            str(destination_address) if destination_address is not None else None
        ),
        payload=str(payload) if payload is not None else None,
    )


class XknxSignalReaderGateway:
    def __init__(
        self,
        profile: EndpointProfile,
        addresses: Sequence[str],
        payload_length: int,
    ) -> None:
        self._connection_state_handler: Callable[[str], None] = lambda state: None
        self._telegram_handler: Callable[[TelegramEvent], None] = lambda event: None
        self._update_handler: Callable[[SignalUpdate], None] = lambda update: None
        self._payload_length = payload_length
        self._xknx = XKNX(
            connection_config=_connection_config(profile),
            telegram_received_cb=self._on_telegram,
            connection_state_changed_cb=self._on_connection_state,
        )
        self._remote_values = {
            address: self._build_remote_value(address) for address in addresses
        }

    @property
    def current_address(self) -> str | None:
        address = self._xknx.current_address
        return str(address) if address is not None else None

    def set_connection_state_handler(self, handler: Callable[[str], None]) -> None:
        self._connection_state_handler = handler

    def set_telegram_handler(self, handler: Callable[[TelegramEvent], None]) -> None:
        self._telegram_handler = handler

    def set_update_handler(self, handler: Callable[[SignalUpdate], None]) -> None:
        self._update_handler = handler

    async def start(self) -> None:
        await self._xknx.start()

    async def stop(self) -> None:
        await self._xknx.stop()

    async def read(self, address: str, timeout: float) -> ReadResult | None:
        reader = ValueReader(
            self._xknx,
            GroupAddress(address),
            timeout_in_seconds=timeout,
        )
        telegram = await reader.read()
        if telegram is None:
            return None
        update = await self._process_update(address, telegram)
        return ReadResult(address=address, telegram=str(telegram), update=update)

    def _build_remote_value(self, address: str) -> RemoteValueRaw:
        return RemoteValueRaw(
            self._xknx,
            payload_length=self._payload_length,
            group_address_state=address,
            sync_state=False,
            device_name=address,
            feature_name="State",
        )

    def _remote_value(self, address: str) -> RemoteValueRaw:
        remote_value = self._remote_values.get(address)
        if remote_value is None:
            remote_value = self._build_remote_value(address)
            self._remote_values[address] = remote_value
        return remote_value

    async def _process_update(
        self,
        address: str,
        telegram: Telegram,
    ) -> SignalUpdate | None:
        remote_value = self._remote_value(address)
        updated = remote_value.process(telegram)
        if inspect.isawaitable(updated):
            updated = await updated
        if not updated:
            return None
        source_address = getattr(telegram, "source_address", None)
        last_telegram = remote_value.telegram or telegram
        return SignalUpdate(
            address=address,
            value=remote_value.value,
            telegram=str(last_telegram),
            source_address=str(source_address) if source_address is not None else None,
        )

    async def _handle_telegram(self, telegram: Telegram) -> None:
        self._telegram_handler(_telegram_event(telegram))
        for address in tuple(self._remote_values):
            update = await self._process_update(address, telegram)
            if update is not None:
                self._update_handler(update)

    def _on_telegram(self, telegram: Telegram) -> None:
        _schedule(self._handle_telegram(telegram))

    def _on_connection_state(self, state: Any) -> None:
        self._connection_state_handler(str(state))


class XknxBlinkGateway:
    def __init__(
        self,
        profile: EndpointProfile,
        switch_address: str,
        feedback_address: str,
    ) -> None:
        self._connection_state_handler: Callable[[str], None] = lambda state: None
        self._telegram_handler: Callable[[TelegramEvent], None] = lambda event: None
        self._feedback_handler: Callable[[FeedbackSnapshot], None] = lambda snapshot: None
        self._feedback_snapshot = FeedbackSnapshot(is_on=None, last_telegram=None)
        self._xknx = XKNX(
            connection_config=_connection_config(profile),
            telegram_received_cb=self._on_telegram,
            connection_state_changed_cb=self._on_connection_state,
            device_updated_cb=self._on_device_updated,
        )
        self._feedback_sensor = BinarySensor(
            self._xknx,
            name="DemoLightFeedback",
            group_address_state=feedback_address,
            sync_state=False,
        )
        self._switch = Switch(
            self._xknx,
            name="DemoLight",
            group_address=switch_address,
            group_address_state=feedback_address,
            sync_state=False,
        )

    @property
    def current_address(self) -> str | None:
        address = self._xknx.current_address
        return str(address) if address is not None else None

    def set_connection_state_handler(self, handler: Callable[[str], None]) -> None:
        self._connection_state_handler = handler

    def set_telegram_handler(self, handler: Callable[[TelegramEvent], None]) -> None:
        self._telegram_handler = handler

    def set_feedback_handler(
        self,
        handler: Callable[[FeedbackSnapshot], None],
    ) -> None:
        self._feedback_handler = handler

    async def start(self) -> None:
        await self._xknx.start()

    async def stop(self) -> None:
        await self._xknx.stop()

    async def set_on(self) -> None:
        await self._switch.set_on()

    async def set_off(self) -> None:
        await self._switch.set_off()

    def feedback_snapshot(self) -> FeedbackSnapshot:
        sensor_telegram = self._feedback_sensor.last_telegram
        if sensor_telegram is not None:
            return FeedbackSnapshot(
                is_on=self._feedback_sensor.is_on(),
                last_telegram=str(sensor_telegram),
            )
        return self._feedback_snapshot

    def _on_connection_state(self, state: Any) -> None:
        self._connection_state_handler(str(state))

    def _on_telegram(self, telegram: Telegram) -> None:
        self._telegram_handler(_telegram_event(telegram))

    def _on_device_updated(self, device: object) -> None:
        if not isinstance(device, BinarySensor):
            return
        snapshot = FeedbackSnapshot(
            is_on=device.is_on(),
            last_telegram=str(device.last_telegram) if device.last_telegram is not None else None,
        )
        self._feedback_snapshot = snapshot
        self._feedback_handler(snapshot)
