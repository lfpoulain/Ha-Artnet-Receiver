from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_BLUE_CHANNEL,
    CONF_CHANNEL,
    CONF_COLD_WHITE_CHANNEL,
    CONF_COLOR_TEMP_CHANNEL,
    CONF_GREEN_CHANNEL,
    CONF_PROFILE,
    CONF_RED_CHANNEL,
    CONF_WARM_WHITE_CHANNEL,
    CONF_WHITE_CHANNEL,
    DMX_CHANNEL_MAX,
    DMX_CHANNEL_MIN,
    PROFILE_COLOR_TEMP,
    PROFILE_DIMMER,
    PROFILE_RGB,
    PROFILE_RGBW,
    PROFILE_RGBWW,
    PROFILE_SWITCH,
    SUPPORTED_ENTITY_DOMAINS,
)

RGB_COLOR_MODES = {
    ColorMode.HS,
    ColorMode.RGB,
    ColorMode.RGBW,
    ColorMode.RGBWW,
    ColorMode.XY,
}
RGBW_COLOR_MODES = {
    ColorMode.RGBW,
    ColorMode.RGBWW,
}
RGBWW_COLOR_MODES = {
    ColorMode.RGBWW,
}
BRIGHTNESS_COLOR_MODES = RGB_COLOR_MODES | {
    ColorMode.BRIGHTNESS,
    ColorMode.COLOR_TEMP,
    ColorMode.WHITE,
}


def config_from_entry(entry: ConfigEntry) -> dict[str, Any]:
    return {
        **entry.data,
        **entry.options,
    }


def build_unique_id(host: str, port: int) -> str:
    return f"{host}:{int(port)}"


def supported_profiles_for_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    domain = entity_id.split(".", 1)[0]
    if domain == "switch":
        return [PROFILE_SWITCH]
    if domain != "light":
        return []

    state = hass.states.get(entity_id)
    if state is None:
        return []

    profiles = [PROFILE_SWITCH]
    supported_color_modes = set(state.attributes.get(ATTR_SUPPORTED_COLOR_MODES, []))
    if not supported_color_modes:
        if state.attributes.get("brightness") is not None:
            profiles.append(PROFILE_DIMMER)
        return profiles

    if supported_color_modes.intersection(BRIGHTNESS_COLOR_MODES):
        profiles.append(PROFILE_DIMMER)
    if supported_color_modes.intersection(RGB_COLOR_MODES):
        profiles.append(PROFILE_RGB)
    if supported_color_modes.intersection(RGBW_COLOR_MODES):
        profiles.append(PROFILE_RGBW)
    if supported_color_modes.intersection(RGBWW_COLOR_MODES):
        profiles.append(PROFILE_RGBWW)
    if ColorMode.COLOR_TEMP in supported_color_modes:
        profiles.append(PROFILE_COLOR_TEMP)
    return profiles


def build_mapping(user_input: dict[str, Any]) -> dict[str, Any]:
    profile = str(user_input[CONF_PROFILE])
    mapping: dict[str, Any] = {
        CONF_ENTITY_ID: str(user_input[CONF_ENTITY_ID]),
        CONF_PROFILE: profile,
    }
    if profile == PROFILE_RGB:
        mapping[CONF_CHANNEL] = int(user_input[CONF_CHANNEL])
        mapping[CONF_RED_CHANNEL] = int(user_input[CONF_RED_CHANNEL])
        mapping[CONF_GREEN_CHANNEL] = int(user_input[CONF_GREEN_CHANNEL])
        mapping[CONF_BLUE_CHANNEL] = int(user_input[CONF_BLUE_CHANNEL])
    elif profile == PROFILE_RGBW:
        mapping[CONF_CHANNEL] = int(user_input[CONF_CHANNEL])
        mapping[CONF_RED_CHANNEL] = int(user_input[CONF_RED_CHANNEL])
        mapping[CONF_GREEN_CHANNEL] = int(user_input[CONF_GREEN_CHANNEL])
        mapping[CONF_BLUE_CHANNEL] = int(user_input[CONF_BLUE_CHANNEL])
        mapping[CONF_WHITE_CHANNEL] = int(user_input[CONF_WHITE_CHANNEL])
    elif profile == PROFILE_RGBWW:
        mapping[CONF_CHANNEL] = int(user_input[CONF_CHANNEL])
        mapping[CONF_RED_CHANNEL] = int(user_input[CONF_RED_CHANNEL])
        mapping[CONF_GREEN_CHANNEL] = int(user_input[CONF_GREEN_CHANNEL])
        mapping[CONF_BLUE_CHANNEL] = int(user_input[CONF_BLUE_CHANNEL])
        mapping[CONF_COLD_WHITE_CHANNEL] = int(user_input[CONF_COLD_WHITE_CHANNEL])
        mapping[CONF_WARM_WHITE_CHANNEL] = int(user_input[CONF_WARM_WHITE_CHANNEL])
    elif profile == PROFILE_COLOR_TEMP:
        mapping[CONF_CHANNEL] = int(user_input[CONF_CHANNEL])
        mapping[CONF_COLOR_TEMP_CHANNEL] = int(user_input[CONF_COLOR_TEMP_CHANNEL])
    else:
        mapping[CONF_CHANNEL] = int(user_input[CONF_CHANNEL])
    return mapping


def channels_for_mapping(mapping: dict[str, Any]) -> list[int]:
    if mapping[CONF_PROFILE] == PROFILE_RGB:
        return [
            int(mapping[CONF_CHANNEL]),
            int(mapping[CONF_RED_CHANNEL]),
            int(mapping[CONF_GREEN_CHANNEL]),
            int(mapping[CONF_BLUE_CHANNEL]),
        ]
    elif mapping[CONF_PROFILE] == PROFILE_RGBW:
        return [
            int(mapping[CONF_CHANNEL]),
            int(mapping[CONF_RED_CHANNEL]),
            int(mapping[CONF_GREEN_CHANNEL]),
            int(mapping[CONF_BLUE_CHANNEL]),
            int(mapping[CONF_WHITE_CHANNEL]),
        ]
    elif mapping[CONF_PROFILE] == PROFILE_RGBWW:
        return [
            int(mapping[CONF_CHANNEL]),
            int(mapping[CONF_RED_CHANNEL]),
            int(mapping[CONF_GREEN_CHANNEL]),
            int(mapping[CONF_BLUE_CHANNEL]),
            int(mapping[CONF_COLD_WHITE_CHANNEL]),
            int(mapping[CONF_WARM_WHITE_CHANNEL]),
        ]
    elif mapping[CONF_PROFILE] == PROFILE_COLOR_TEMP:
        return [
            int(mapping[CONF_CHANNEL]),
            int(mapping[CONF_COLOR_TEMP_CHANNEL]),
        ]
    return [int(mapping[CONF_CHANNEL])]


def suggest_next_channel(mappings: list[dict[str, Any]]) -> int:
    used_channels = [
        channel
        for mapping in mappings
        for channel in channels_for_mapping(mapping)
    ]
    if not used_channels:
        return DMX_CHANNEL_MIN
    return min(max(used_channels) + 1, DMX_CHANNEL_MAX)


def mapping_label(hass: HomeAssistant, mapping: dict[str, Any]) -> str:
    entity_id = str(mapping[CONF_ENTITY_ID])
    state = hass.states.get(entity_id)
    entity_name = state.name if state is not None else entity_id
    if mapping[CONF_PROFILE] == PROFILE_RGB:
        channel_summary = (
            f"DIM {mapping[CONF_CHANNEL]} / R{mapping[CONF_RED_CHANNEL]} / G{mapping[CONF_GREEN_CHANNEL]} / B{mapping[CONF_BLUE_CHANNEL]}"
        )
    elif mapping[CONF_PROFILE] == PROFILE_RGBW:
        channel_summary = (
            f"DIM {mapping[CONF_CHANNEL]} / R{mapping[CONF_RED_CHANNEL]} / G{mapping[CONF_GREEN_CHANNEL]} / B{mapping[CONF_BLUE_CHANNEL]} / W{mapping[CONF_WHITE_CHANNEL]}"
        )
    elif mapping[CONF_PROFILE] == PROFILE_RGBWW:
        channel_summary = (
            f"DIM {mapping[CONF_CHANNEL]} / R{mapping[CONF_RED_CHANNEL]} / G{mapping[CONF_GREEN_CHANNEL]} / B{mapping[CONF_BLUE_CHANNEL]} / CW{mapping[CONF_COLD_WHITE_CHANNEL]} / WW{mapping[CONF_WARM_WHITE_CHANNEL]}"
        )
    elif mapping[CONF_PROFILE] == PROFILE_COLOR_TEMP:
        channel_summary = (
            f"DIM {mapping[CONF_CHANNEL]} / CT {mapping[CONF_COLOR_TEMP_CHANNEL]}"
        )
    else:
        channel_summary = f"CH {mapping[CONF_CHANNEL]}"
    return f"{entity_name} ({mapping[CONF_PROFILE]} - {channel_summary})"


def validate_mapping(
    hass: HomeAssistant,
    mapping: dict[str, Any],
    existing_mappings: list[dict[str, Any]],
    edited_entity_id: str | None = None,
) -> dict[str, str]:
    entity_id = str(mapping[CONF_ENTITY_ID])
    domain = entity_id.split(".", 1)[0]
    state = hass.states.get(entity_id)

    if domain not in SUPPORTED_ENTITY_DOMAINS:
        return {"base": "entity_not_supported"}
    if state is None:
        return {"base": "entity_not_found"}

    if any(
        existing[CONF_ENTITY_ID] == entity_id and existing[CONF_ENTITY_ID] != edited_entity_id
        for existing in existing_mappings
    ):
        return {"base": "entity_already_added"}

    supported_profiles = supported_profiles_for_entity(hass, entity_id)
    if mapping[CONF_PROFILE] not in supported_profiles:
        return {"base": "invalid_profile"}

    channels = channels_for_mapping(mapping)
    if any(channel < DMX_CHANNEL_MIN or channel > DMX_CHANNEL_MAX for channel in channels):
        return {"base": "channel_out_of_range"}
    if len(channels) != len(set(channels)):
        return {"base": "channel_conflict"}

    occupied_channels = {
        channel
        for existing in existing_mappings
        if existing[CONF_ENTITY_ID] != edited_entity_id
        for channel in channels_for_mapping(existing)
    }
    if occupied_channels.intersection(channels):
        return {"base": "channel_conflict"}

    return {}
