from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helpers import config_from_entry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    receiver = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    config = config_from_entry(entry)
    return {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": config,
            "configured_mappings": config.get("mappings", []),
        },
        "runtime": receiver.diagnostics if receiver is not None else None,
    }
