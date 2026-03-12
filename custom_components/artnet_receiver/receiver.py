from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, CONF_HOST, CONF_PORT, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    ARTNET_HEADER,
    ARTNET_OPCODE_DMX,
    CONF_BLUE_CHANNEL,
    CONF_CHANNEL,
    CONF_COLD_WHITE_CHANNEL,
    CONF_COLOR_TEMP_CHANNEL,
    CONF_GREEN_CHANNEL,
    CONF_MAPPINGS,
    CONF_POLLING_MODE,
    CONF_PROFILE,
    CONF_RED_CHANNEL,
    CONF_UNIVERSE,
    CONF_WARM_WHITE_CHANNEL,
    CONF_WHITE_CHANNEL,
    DEFAULT_POLLING_MODE,
    DIAGNOSTIC_EVENT_INTERVAL_SECONDS,
    DMX_SWITCH_ON_THRESHOLD,
    POLLING_MODE_TO_INTERVAL_MS,
    PROFILE_COLOR_TEMP,
    PROFILE_DIMMER,
    PROFILE_RGB,
    PROFILE_RGB_COLOR_TEMP,
    PROFILE_RGBW,
    PROFILE_RGBWW,
    PROFILE_SWITCH,
)
from .helpers import config_from_entry

_LOGGER = logging.getLogger(__name__)

DEFAULT_MIN_MIREDS = 153
DEFAULT_MAX_MIREDS = 500
BIND_RETRY_ATTEMPTS = 5
BIND_RETRY_DELAY_SECONDS = 1
SERVICE_ERROR_LOG_INTERVAL_SECONDS = 60

@dataclass(frozen=True, slots=True)
class DmaixMapping:
    entity_id: str
    profile: str
    channels: tuple[int, ...]


class ArtNetProtocol(asyncio.DatagramProtocol):
    def __init__(self, receiver: "DmaixReceiver") -> None:
        self._receiver = receiver

    def datagram_received(self, data: bytes, addr) -> None:
        if len(data) < 18 or not data.startswith(ARTNET_HEADER):
            return

        opcode = int.from_bytes(data[8:10], "little")
        if opcode != ARTNET_OPCODE_DMX:
            return

        universe = int.from_bytes(data[14:16], "little")
        if universe != self._receiver.universe:
            return

        payload_length = int.from_bytes(data[16:18], "big")
        dmx_data = data[18 : 18 + payload_length]
        if not dmx_data:
            return

        self._receiver.process_dmx_frame(
            dmx_data,
            source_address=addr[0] if addr else None,
            universe=universe,
        )

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("Art-Net socket error: %s", exc)


class DmaixReceiver:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config = config_from_entry(entry)
        self.bind_host = str(self.config[CONF_HOST])
        self.bind_port = int(self.config[CONF_PORT])
        self.universe = int(self.config[CONF_UNIVERSE])
        self.polling_mode = str(self.config.get(CONF_POLLING_MODE, DEFAULT_POLLING_MODE))
        self.service_call_interval_ms = int(
            POLLING_MODE_TO_INTERVAL_MS.get(self.polling_mode, POLLING_MODE_TO_INTERVAL_MS[DEFAULT_POLLING_MODE])
        )
        self._mappings = tuple(self._load_mappings(self.config.get(CONF_MAPPINGS, [])))
        self._transport: asyncio.DatagramTransport | None = None
        self._remove_interval: CALLBACK_TYPE | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._last_applied: dict[str, bool | int | tuple[int, ...]] = {}
        self._effective_bind_host = self.bind_host
        self._last_packet_at = None
        self._last_source_address: str | None = None
        self._last_universe_received: int | None = None
        self._last_error: str | None = None
        self._last_frame = bytearray(512)
        self._last_listener_notification = 0.0
        self._last_logged_error_signature: tuple[str, str, str] | None = None
        self._last_logged_error_at = 0.0
        self._last_service_call: dict[str, Any] | None = None
        self._pending_service_calls: dict[str, tuple[str, str, dict[str, Any]]] = {}
        self._service_call_tasks: dict[str, asyncio.Task] = {}
        self._last_service_call_sent_at: dict[str, float] = {}
        self.packets_received = 0
        self.service_calls_sent = 0

    async def async_start(self) -> None:
        bind_host = self.bind_host
        remaining_attempts = BIND_RETRY_ATTEMPTS
        while True:
            try:
                transport, _ = await self.hass.loop.create_datagram_endpoint(
                    lambda: ArtNetProtocol(self),
                    local_addr=(bind_host, self.bind_port),
                )
                self._effective_bind_host = bind_host
                break
            except OSError as err:
                if err.errno == 99 and bind_host != "0.0.0.0":
                    _LOGGER.warning(
                        "Configured Art-Net bind address %s is not available on this host, falling back to 0.0.0.0:%s",
                        bind_host,
                        self.bind_port,
                    )
                    bind_host = "0.0.0.0"
                    continue
                if err.errno in {98, 10048} and remaining_attempts > 1:
                    remaining_attempts -= 1
                    _LOGGER.warning(
                        "Art-Net socket %s:%s is temporarily busy, retrying in %s second(s) (%s attempt(s) remaining)",
                        bind_host,
                        self.bind_port,
                        BIND_RETRY_DELAY_SECONDS,
                        remaining_attempts,
                    )
                    await asyncio.sleep(BIND_RETRY_DELAY_SECONDS)
                    continue
                raise

        self._transport = transport
        self._remove_interval = async_track_time_interval(
            self.hass,
            self._handle_diagnostic_tick,
            timedelta(seconds=DIAGNOSTIC_EVENT_INTERVAL_SECONDS),
        )
        _LOGGER.info(
            "ArtNet Receiver listening on %s:%s for Art-Net universe %s with %s mapped entities",
            self._effective_bind_host,
            self.bind_port,
            self.universe,
            len(self._mappings),
        )
        self._notify_listeners(force=True)

    async def async_stop(self) -> None:
        if self._remove_interval is not None:
            self._remove_interval()
            self._remove_interval = None
        for task in list(self._service_call_tasks.values()):
            task.cancel()
        self._service_call_tasks.clear()
        self._pending_service_calls.clear()
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        await asyncio.sleep(0)

    @property
    def is_active(self) -> bool:
        if self._last_packet_at is None:
            return False
        return (dt_util.utcnow() - self._last_packet_at) <= timedelta(seconds=5)

    @property
    def diagnostics(self) -> dict[str, Any]:
        return {
            "configured_bind_host": self.bind_host,
            "effective_bind_host": self._effective_bind_host,
            "port": self.bind_port,
            "universe": self.universe,
            "polling_mode": self.polling_mode,
            "service_call_interval_ms": self.service_call_interval_ms,
            "mappings_count": len(self._mappings),
            "mapped_entities": [mapping.entity_id for mapping in self._mappings],
            "configured_mappings": self._mapping_diagnostics(),
            "packets_received": self.packets_received,
            "active_service_workers": len(self._service_call_tasks),
            "queued_service_calls": len(self._pending_service_calls),
            "service_calls_sent": self.service_calls_sent,
            "last_service_call": self._last_service_call,
            "last_packet_at": self._last_packet_at.isoformat() if self._last_packet_at is not None else None,
            "last_source_address": self._last_source_address,
            "last_universe_received": self._last_universe_received,
            "last_error": self._last_error,
            "is_active": self.is_active,
        }

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    def process_dmx_frame(
        self,
        dmx_data: bytes,
        source_address: str | None = None,
        universe: int | None = None,
    ) -> None:
        self.packets_received += 1
        self._last_packet_at = dt_util.utcnow()
        self._last_source_address = source_address
        self._last_universe_received = universe if universe is not None else self.universe
        frame_length = min(len(dmx_data), len(self._last_frame))
        self._last_frame[:frame_length] = dmx_data[:frame_length]

        for mapping in self._mappings:
            values = self._read_mapping_values(mapping, dmx_data)
            if values is None:
                continue

            state_key = self._build_state_key(mapping, values)
            if self._last_applied.get(mapping.entity_id) == state_key:
                continue

            self._last_applied[mapping.entity_id] = state_key
            self._queue_service_call(mapping, values)

        self._notify_listeners()

    def test_channel(self, channel: int, value: int) -> None:
        test_frame = bytearray(self._last_frame)
        test_frame[channel - 1] = value
        self.process_dmx_frame(
            bytes(test_frame),
            source_address="service:test_channel",
            universe=self.universe,
        )

    def test_mapping(
        self,
        entity_id: str,
        value: int | None = None,
        red: int | None = None,
        green: int | None = None,
        blue: int | None = None,
        white: int | None = None,
        cold_white: int | None = None,
        warm_white: int | None = None,
        color_temp: int | None = None,
    ) -> None:
        mapping = next(
            (current for current in self._mappings if current.entity_id == entity_id),
            None,
        )
        if mapping is None:
            raise ValueError(f"Mapping not found for {entity_id}")

        if mapping.profile == PROFILE_RGB:
            if value is None or red is None or green is None or blue is None:
                raise ValueError("RGB mappings require dimmer, red, green and blue values")
            values = (value, red, green, blue)
        elif mapping.profile == PROFILE_RGB_COLOR_TEMP:
            if (
                value is None
                or red is None
                or green is None
                or blue is None
                or color_temp is None
            ):
                raise ValueError(
                    "RGB + color temperature mappings require dimmer, red, green, blue and color temperature values"
                )
            values = (value, red, green, blue, color_temp)
        elif mapping.profile == PROFILE_RGBW:
            if value is None or red is None or green is None or blue is None or white is None:
                raise ValueError("RGBW mappings require dimmer, red, green, blue and white values")
            values = (value, red, green, blue, white)
        elif mapping.profile == PROFILE_RGBWW:
            if (
                value is None
                or red is None
                or green is None
                or blue is None
                or cold_white is None
                or warm_white is None
            ):
                raise ValueError(
                    "RGBWW mappings require dimmer, red, green, blue, cold white and warm white values"
                )
            values = (value, red, green, blue, cold_white, warm_white)
        elif mapping.profile == PROFILE_COLOR_TEMP:
            if value is None or color_temp is None:
                raise ValueError("Color temperature mappings require dimmer and color temperature values")
            values = (value, color_temp)
        else:
            if value is None:
                raise ValueError("Single-channel mappings require a value")
            values = (value,)

        self._last_applied[mapping.entity_id] = self._build_state_key(mapping, values)
        self._queue_service_call(mapping, values)
        self._notify_listeners(force=True)

    @callback
    def _handle_diagnostic_tick(self, now) -> None:
        self._notify_listeners(force=True)

    def _notify_listeners(self, force: bool = False) -> None:
        now = self.hass.loop.time()
        if not force and now - self._last_listener_notification < DIAGNOSTIC_EVENT_INTERVAL_SECONDS:
            return
        self._last_listener_notification = now
        for listener in list(self._listeners):
            listener()

    def _queue_service_call(self, mapping: DmaixMapping, values: tuple[int, ...]) -> None:
        domain = mapping.entity_id.split(".", 1)[0]
        service_data: dict[str, Any] = {CONF_ENTITY_ID: mapping.entity_id}

        if mapping.profile == PROFILE_SWITCH:
            service = SERVICE_TURN_ON if values[0] >= DMX_SWITCH_ON_THRESHOLD else SERVICE_TURN_OFF
        elif mapping.profile == PROFILE_DIMMER:
            if values[0] == 0:
                service = SERVICE_TURN_OFF
            else:
                service = SERVICE_TURN_ON
                service_data[ATTR_BRIGHTNESS] = values[0]
        elif mapping.profile == PROFILE_RGB:
            if values[0] == 0:
                service = SERVICE_TURN_OFF
            else:
                service = SERVICE_TURN_ON
                service_data[ATTR_BRIGHTNESS] = values[0]
                service_data[ATTR_RGB_COLOR] = [values[1], values[2], values[3]]
        elif mapping.profile == PROFILE_RGB_COLOR_TEMP:
            if values[0] == 0:
                service = SERVICE_TURN_OFF
            else:
                service = SERVICE_TURN_ON
                service_data[ATTR_BRIGHTNESS] = values[0]
                if any(channel > 0 for channel in values[1:4]):
                    service_data[ATTR_RGB_COLOR] = [values[1], values[2], values[3]]
                else:
                    service_data["color_temp_kelvin"] = self._map_dmx_to_color_temp_kelvin(
                        mapping.entity_id,
                        values[4],
                    )
        elif mapping.profile == PROFILE_RGBW:
            if values[0] == 0:
                service = SERVICE_TURN_OFF
            else:
                service = SERVICE_TURN_ON
                service_data[ATTR_BRIGHTNESS] = values[0]
                service_data["rgbw_color"] = [values[1], values[2], values[3], values[4]]
        elif mapping.profile == PROFILE_RGBWW:
            if values[0] == 0:
                service = SERVICE_TURN_OFF
            else:
                service = SERVICE_TURN_ON
                service_data[ATTR_BRIGHTNESS] = values[0]
                service_data["rgbww_color"] = [
                    values[1],
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                ]
        elif mapping.profile == PROFILE_COLOR_TEMP:
            if values[0] == 0:
                service = SERVICE_TURN_OFF
            else:
                service = SERVICE_TURN_ON
                service_data[ATTR_BRIGHTNESS] = values[0]
                service_data["color_temp_kelvin"] = self._map_dmx_to_color_temp_kelvin(
                    mapping.entity_id,
                    values[1],
                )
        else:
            raise ValueError(f"Unsupported profile: {mapping.profile}")

        entity_id = mapping.entity_id
        self._pending_service_calls[entity_id] = (domain, service, service_data)
        task = self._service_call_tasks.get(entity_id)
        if task is None or task.done():
            self._service_call_tasks[entity_id] = self.hass.async_create_task(
                self._async_process_service_call_queue(entity_id)
            )

    async def _async_process_service_call_queue(self, entity_id: str) -> None:
        try:
            interval_seconds = self.service_call_interval_ms / 1000
            while entity_id in self._pending_service_calls:
                last_sent_at = self._last_service_call_sent_at.get(entity_id)
                if last_sent_at is None:
                    await asyncio.sleep(interval_seconds)
                else:
                    wait_time = max(0.0, interval_seconds - (self.hass.loop.time() - last_sent_at))
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

                queued_call = self._pending_service_calls.pop(entity_id, None)
                if queued_call is None:
                    continue

                domain, service, service_data = queued_call
                self.service_calls_sent += 1
                self._last_service_call = {
                    "entity_id": entity_id,
                    "domain": domain,
                    "service": service,
                    "service_data": dict(service_data),
                }
                self._last_service_call_sent_at[entity_id] = self.hass.loop.time()
                await self._async_call_service(domain, service, service_data)
                self._notify_listeners(force=True)
        except asyncio.CancelledError:
            raise
        finally:
            self._service_call_tasks.pop(entity_id, None)

    async def _async_call_service(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any],
    ) -> None:
        try:
            await self.hass.services.async_call(
                domain,
                service,
                service_data,
                blocking=True,
            )
        except Exception as err:
            error_signature = (domain, service, str(err))
            self._last_error = str(err)
            if (
                self._last_logged_error_signature == error_signature
                and self.hass.loop.time() - self._last_logged_error_at < SERVICE_ERROR_LOG_INTERVAL_SECONDS
            ):
                _LOGGER.debug(
                    "Suppressing repeated ArtNet Receiver service error for %s.%s: %s",
                    domain,
                    service,
                    err,
                )
                self._notify_listeners(force=True)
                return
            self._last_logged_error_signature = error_signature
            self._last_logged_error_at = self.hass.loop.time()
            _LOGGER.warning(
                "ArtNet Receiver service call failed for %s.%s with %s: %s",
                domain,
                service,
                service_data,
                err,
            )
            self._notify_listeners(force=True)

    @staticmethod
    def _build_state_key(
        mapping: DmaixMapping, values: tuple[int, ...]
    ) -> bool | int | tuple[int, ...]:
        if mapping.profile == PROFILE_SWITCH:
            return values[0] >= DMX_SWITCH_ON_THRESHOLD
        if mapping.profile == PROFILE_DIMMER:
            return values[0]
        return values

    @staticmethod
    def _read_mapping_values(
        mapping: DmaixMapping, dmx_data: bytes
    ) -> tuple[int, ...] | None:
        values: list[int] = []
        for channel in mapping.channels:
            channel_index = channel - 1
            if channel_index < 0 or channel_index >= len(dmx_data):
                return None
            values.append(dmx_data[channel_index])
        return tuple(values)

    @staticmethod
    def _load_mappings(raw_mappings: list[dict[str, Any]]) -> list[DmaixMapping]:
        mappings: list[DmaixMapping] = []
        for raw_mapping in raw_mappings:
            if raw_mapping[CONF_PROFILE] == PROFILE_RGB:
                channels = (
                    int(raw_mapping[CONF_CHANNEL]),
                    int(raw_mapping[CONF_RED_CHANNEL]),
                    int(raw_mapping[CONF_GREEN_CHANNEL]),
                    int(raw_mapping[CONF_BLUE_CHANNEL]),
                )
            elif raw_mapping[CONF_PROFILE] == PROFILE_RGB_COLOR_TEMP:
                channels = (
                    int(raw_mapping[CONF_CHANNEL]),
                    int(raw_mapping[CONF_RED_CHANNEL]),
                    int(raw_mapping[CONF_GREEN_CHANNEL]),
                    int(raw_mapping[CONF_BLUE_CHANNEL]),
                    int(raw_mapping[CONF_COLOR_TEMP_CHANNEL]),
                )
            elif raw_mapping[CONF_PROFILE] == PROFILE_RGBW:
                channels = (
                    int(raw_mapping[CONF_CHANNEL]),
                    int(raw_mapping[CONF_RED_CHANNEL]),
                    int(raw_mapping[CONF_GREEN_CHANNEL]),
                    int(raw_mapping[CONF_BLUE_CHANNEL]),
                    int(raw_mapping[CONF_WHITE_CHANNEL]),
                )
            elif raw_mapping[CONF_PROFILE] == PROFILE_RGBWW:
                channels = (
                    int(raw_mapping[CONF_CHANNEL]),
                    int(raw_mapping[CONF_RED_CHANNEL]),
                    int(raw_mapping[CONF_GREEN_CHANNEL]),
                    int(raw_mapping[CONF_BLUE_CHANNEL]),
                    int(raw_mapping[CONF_COLD_WHITE_CHANNEL]),
                    int(raw_mapping[CONF_WARM_WHITE_CHANNEL]),
                )
            elif raw_mapping[CONF_PROFILE] == PROFILE_COLOR_TEMP:
                channels = (
                    int(raw_mapping[CONF_CHANNEL]),
                    int(raw_mapping[CONF_COLOR_TEMP_CHANNEL]),
                )
            else:
                channels = (int(raw_mapping[CONF_CHANNEL]),)

            mappings.append(
                DmaixMapping(
                    entity_id=str(raw_mapping[CONF_ENTITY_ID]),
                    profile=str(raw_mapping[CONF_PROFILE]),
                    channels=channels,
                )
            )
        return mappings

    def _mapping_diagnostics(self) -> list[dict[str, Any]]:
        return [
            {
                "entity_id": mapping.entity_id,
                "profile": mapping.profile,
                "channels": list(mapping.channels),
            }
            for mapping in self._mappings
        ]

    def _map_dmx_to_color_temp_kelvin(self, entity_id: str, dmx_value: int) -> int:
        state = self.hass.states.get(entity_id)
        min_mireds = DEFAULT_MIN_MIREDS
        max_mireds = DEFAULT_MAX_MIREDS
        if state is not None:
            min_mireds = int(state.attributes.get("min_mireds", min_mireds))
            max_mireds = int(state.attributes.get("max_mireds", max_mireds))
        if max_mireds <= min_mireds:
            return int(round(1000000 / max(min_mireds, 1)))
        mireds = int(
            math.floor(
                min_mireds
                + ((max_mireds - min_mireds) * (dmx_value / 255))
            )
        )
        return int(round(1000000 / max(mireds, 1)))
