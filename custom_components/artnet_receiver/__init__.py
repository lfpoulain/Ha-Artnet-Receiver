from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError

from .const import (
    CONF_BLUE,
    CONF_CHANNEL,
    CONF_COLOR_TEMP,
    CONF_COLD_WHITE,
    CONF_ENTRY_ID,
    CONF_GREEN,
    CONF_MAPPING_ENTITY,
    CONF_RED,
    CONF_VALUE,
    CONF_WARM_WHITE,
    CONF_WHITE,
    DOMAIN,
    PLATFORMS,
    SERVICE_TEST_CHANNEL,
    SERVICE_TEST_MAPPING,
)
from .receiver import DmaixReceiver


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _async_register_services(hass)
    receiver = DmaixReceiver(hass, entry)
    try:
        await receiver.async_start()
    except OSError as err:
        raise ConfigEntryNotReady(f"Unable to start Art-Net receiver: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = receiver
    hass.data[DOMAIN][f"listener_{entry.entry_id}"] = entry.add_update_listener(async_reload_entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    receiver = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    listener = hass.data.get(DOMAIN, {}).pop(f"listener_{entry.entry_id}", None)
    if listener is not None:
        listener()
    if receiver is not None:
        await receiver.async_stop()

    if DOMAIN in hass.data and hass.data[DOMAIN] == {"services_registered": True}:
        return True

    if DOMAIN in hass.data and not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _build_test_channel_handler(hass: HomeAssistant):
    async def handle(call: ServiceCall) -> None:
        receiver = _resolve_receiver(hass, call.data.get(CONF_ENTRY_ID))
        receiver.test_channel(
            int(call.data[CONF_CHANNEL]),
            int(call.data[CONF_VALUE]),
        )

    return handle


def _build_test_mapping_handler(hass: HomeAssistant):
    async def handle(call: ServiceCall) -> None:
        receiver = _resolve_receiver(hass, call.data.get(CONF_ENTRY_ID))
        receiver.test_mapping(
            str(call.data[CONF_MAPPING_ENTITY]),
            value=call.data.get(CONF_VALUE),
            red=call.data.get(CONF_RED),
            green=call.data.get(CONF_GREEN),
            blue=call.data.get(CONF_BLUE),
            white=call.data.get(CONF_WHITE),
            cold_white=call.data.get(CONF_COLD_WHITE),
            warm_white=call.data.get(CONF_WARM_WHITE),
            color_temp=call.data.get(CONF_COLOR_TEMP),
        )

    return handle


def _resolve_receiver(hass: HomeAssistant, entry_id: str | None) -> DmaixReceiver:
    domain_data = hass.data.get(DOMAIN, {})
    receivers = {
        key: value
        for key, value in domain_data.items()
        if isinstance(value, DmaixReceiver)
    }
    if entry_id is not None:
        receiver = receivers.get(entry_id)
        if receiver is None:
            raise HomeAssistantError(f"ArtNet Receiver entry not found: {entry_id}")
        return receiver
    if len(receivers) == 1:
        return next(iter(receivers.values()))
    raise HomeAssistantError("Multiple ArtNet Receiver entries exist, entry_id is required")


def _async_register_services(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("services_registered"):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_CHANNEL,
        _build_test_channel_handler(hass),
        schema=vol.Schema(
            {
                vol.Optional(CONF_ENTRY_ID): str,
                vol.Required(CONF_CHANNEL): vol.All(int, vol.Range(min=1, max=512)),
                vol.Required(CONF_VALUE): vol.All(int, vol.Range(min=0, max=255)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TEST_MAPPING,
        _build_test_mapping_handler(hass),
        schema=vol.Schema(
            {
                vol.Optional(CONF_ENTRY_ID): str,
                vol.Required(CONF_MAPPING_ENTITY): str,
                vol.Optional(CONF_VALUE): vol.All(int, vol.Range(min=0, max=255)),
                vol.Optional(CONF_RED): vol.All(int, vol.Range(min=0, max=255)),
                vol.Optional(CONF_GREEN): vol.All(int, vol.Range(min=0, max=255)),
                vol.Optional(CONF_BLUE): vol.All(int, vol.Range(min=0, max=255)),
                vol.Optional(CONF_WHITE): vol.All(int, vol.Range(min=0, max=255)),
                vol.Optional(CONF_COLD_WHITE): vol.All(int, vol.Range(min=0, max=255)),
                vol.Optional(CONF_WARM_WHITE): vol.All(int, vol.Range(min=0, max=255)),
                vol.Optional(CONF_COLOR_TEMP): vol.All(int, vol.Range(min=0, max=255)),
            }
        ),
    )
    domain_data["services_registered"] = True
