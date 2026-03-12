from __future__ import annotations

from collections.abc import Callable
import json
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    receiver = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DmaixActivitySensor(entry, receiver),
            DmaixPacketsSensor(entry, receiver),
            DmaixServiceCallsSensor(entry, receiver),
            DmaixMappingsSensor(entry, receiver),
        ]
    )


class DmaixBaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, receiver) -> None:
        self._entry = entry
        self._receiver = receiver
        self._remove_listener: Callable[[], None] | None = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "ArtNet Receiver",
            "model": "ArtNet Receiver",
        }

    async def async_added_to_hass(self) -> None:
        @callback
        def handle_update() -> None:
            self.async_write_ha_state()

        self._remove_listener = self._receiver.async_add_listener(handle_update)

    async def async_will_remove_from_hass(self) -> None:
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None


class DmaixActivitySensor(DmaixBaseSensor):
    _attr_translation_key = "activity"

    def __init__(self, entry: ConfigEntry, receiver) -> None:
        super().__init__(entry, receiver)
        self._attr_unique_id = f"{entry.entry_id}_activity"

    @property
    def native_value(self) -> str:
        return "active" if self._receiver.is_active else "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._receiver.diagnostics


class DmaixPacketsSensor(DmaixBaseSensor):
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "packets"

    _attr_translation_key = "packets_received"

    def __init__(self, entry: ConfigEntry, receiver) -> None:
        super().__init__(entry, receiver)
        self._attr_unique_id = f"{entry.entry_id}_packets_received"

    @property
    def native_value(self) -> int:
        return self._receiver.packets_received


class DmaixServiceCallsSensor(DmaixBaseSensor):
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "calls"

    _attr_translation_key = "service_calls_sent"

    def __init__(self, entry: ConfigEntry, receiver) -> None:
        super().__init__(entry, receiver)
        self._attr_unique_id = f"{entry.entry_id}_service_calls_sent"

    @property
    def native_value(self) -> int:
        return self._receiver.service_calls_sent


class DmaixMappingsSensor(DmaixBaseSensor):
    _attr_translation_key = "mappings"

    def __init__(self, entry: ConfigEntry, receiver) -> None:
        super().__init__(entry, receiver)
        self._attr_unique_id = f"{entry.entry_id}_mappings"

    @property
    def native_value(self) -> str:
        mappings = self._receiver.diagnostics.get("configured_mappings", [])
        summaries = [self._format_mapping_summary(mapping) for mapping in mappings]
        if not summaries:
            return "No mappings"
        joined = " | ".join(summaries)
        if len(joined) <= 255:
            return joined
        return f"{len(summaries)} mappings configured"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mappings = self._receiver.diagnostics.get("configured_mappings", [])
        summaries = [self._format_mapping_summary(mapping) for mapping in mappings]
        return {
            "count": len(mappings),
            "summary": summaries,
            "mappings": mappings,
            "mappings_json": json.dumps(mappings, ensure_ascii=False),
        }

    @staticmethod
    def _format_mapping_summary(mapping: dict[str, Any]) -> str:
        entity_id = str(mapping.get("entity_id", "unknown"))
        profile = str(mapping.get("profile", "unknown"))
        channels = mapping.get("channels", [])
        channels_text = ",".join(str(channel) for channel in channels)
        return f"{entity_id} [{profile}:{channels_text}]"
