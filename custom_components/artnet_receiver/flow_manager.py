from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import (
    ARTNET_UNIVERSE_MAX,
    ARTNET_UNIVERSE_MIN,
    CONF_ADD_ANOTHER,
    CONF_BLUE_CHANNEL,
    CONF_CHANNEL,
    CONF_COLD_WHITE_CHANNEL,
    CONF_COLOR_TEMP_CHANNEL,
    CONF_GREEN_CHANNEL,
    CONF_MAPPING_ENTITY,
    CONF_MAPPINGS,
    CONF_POLLING_MODE,
    CONF_PROFILE,
    CONF_RED_CHANNEL,
    CONF_UNIVERSE,
    CONF_WARM_WHITE_CHANNEL,
    CONF_WHITE_CHANNEL,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_POLLING_MODE,
    DEFAULT_PORT,
    DEFAULT_UNIVERSE,
    DMX_CHANNEL_MAX,
    DMX_CHANNEL_MIN,
    DOMAIN,
    POLLING_MODE_FAST,
    POLLING_MODE_LOW,
    POLLING_MODE_NORMAL,
    PROFILE_COLOR_TEMP,
    PROFILE_DIMMER,
    PROFILE_RGB,
    PROFILE_RGB_COLOR_TEMP,
    PROFILE_RGBW,
    PROFILE_RGBWW,
    PROFILE_SWITCH,
    SUPPORTED_ENTITY_DOMAINS,
)
from .helpers import (
    build_mapping,
    build_unique_id,
    config_from_entry,
    mapping_label,
    preferred_profile_for_entity,
    suggest_next_channel,
    validate_mapping,
)


class BaseDmaixFlow:
    def _config_schema(self, current_config: dict[str, Any]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=current_config.get(CONF_NAME, DEFAULT_NAME)): str,
                vol.Required(CONF_HOST, default=current_config.get(CONF_HOST, DEFAULT_HOST)): str,
                vol.Required(CONF_PORT, default=int(current_config.get(CONF_PORT, DEFAULT_PORT))): selector(
                    {
                        "number": {
                            "min": 1,
                            "max": 65535,
                            "mode": "box",
                            "step": 1,
                        }
                    }
                ),
                vol.Required(CONF_UNIVERSE, default=int(current_config.get(CONF_UNIVERSE, DEFAULT_UNIVERSE))): selector(
                    {
                        "number": {
                            "min": ARTNET_UNIVERSE_MIN,
                            "max": ARTNET_UNIVERSE_MAX,
                            "mode": "box",
                            "step": 1,
                        }
                    }
                ),
                vol.Required(
                    CONF_POLLING_MODE,
                    default=current_config.get(CONF_POLLING_MODE, DEFAULT_POLLING_MODE),
                ): selector(
                    {
                        "select": {
                            "options": [
                                {"value": POLLING_MODE_FAST, "label": "Fast (50 ms)"},
                                {"value": POLLING_MODE_NORMAL, "label": "Normal (100 ms)"},
                                {"value": POLLING_MODE_LOW, "label": "Low (200 ms)"},
                            ],
                            "mode": "dropdown",
                        }
                    }
                ),
            }
        )

    @staticmethod
    def _profile_options() -> list[dict[str, str]]:
        return [
            {"value": PROFILE_SWITCH, "label": "Switch / prise / relais"},
            {"value": PROFILE_DIMMER, "label": "Dimmer"},
            {"value": PROFILE_RGB, "label": "RGB (4 canaux)"},
            {"value": PROFILE_RGB_COLOR_TEMP, "label": "RGB + température de couleur (5 canaux)"},
            {"value": PROFILE_RGBW, "label": "RGBW (5 canaux)"},
            {"value": PROFILE_RGBWW, "label": "RGBWW (6 canaux)"},
            {"value": PROFILE_COLOR_TEMP, "label": "Color temperature (2 canaux)"},
        ]

    def _mapping_target_schema(
        self,
        defaults: dict[str, Any] | None = None,
        include_add_another: bool = True,
    ) -> vol.Schema:
        defaults = defaults or {}
        schema: dict[Any, Any] = {
            (
                vol.Required(CONF_ENTITY_ID, default=defaults[CONF_ENTITY_ID])
                if CONF_ENTITY_ID in defaults
                else vol.Required(CONF_ENTITY_ID)
            ): selector(
                {
                    "entity": {
                        "domain": list(SUPPORTED_ENTITY_DOMAINS),
                    }
                }
            ),
        }
        if include_add_another:
            schema[
                vol.Required(
                    CONF_ADD_ANOTHER,
                    default=bool(defaults.get(CONF_ADD_ANOTHER, False)),
                )
            ] = bool
        return vol.Schema(schema)

    def _mapping_channels_schema(
        self,
        profile: str,
        mappings: list[dict[str, Any]],
        defaults: dict[str, Any] | None = None,
    ) -> vol.Schema:
        defaults = defaults or {}
        next_channel = suggest_next_channel(mappings)
        schema: dict[Any, Any] = {}

        if profile in {
            PROFILE_SWITCH,
            PROFILE_DIMMER,
            PROFILE_RGB,
            PROFILE_RGB_COLOR_TEMP,
            PROFILE_RGBW,
            PROFILE_RGBWW,
            PROFILE_COLOR_TEMP,
        }:
            schema[vol.Required(CONF_CHANNEL, default=int(defaults.get(CONF_CHANNEL, next_channel)))] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )

        if profile in {PROFILE_RGB, PROFILE_RGB_COLOR_TEMP, PROFILE_RGBW, PROFILE_RGBWW}:
            schema[vol.Required(CONF_RED_CHANNEL, default=int(defaults.get(CONF_RED_CHANNEL, min(next_channel + 1, DMX_CHANNEL_MAX))))] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )
            schema[vol.Required(CONF_GREEN_CHANNEL, default=int(defaults.get(CONF_GREEN_CHANNEL, min(next_channel + 2, DMX_CHANNEL_MAX))))] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )
            schema[vol.Required(CONF_BLUE_CHANNEL, default=int(defaults.get(CONF_BLUE_CHANNEL, min(next_channel + 3, DMX_CHANNEL_MAX))))] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )

        if profile == PROFILE_RGBW:
            schema[vol.Required(CONF_WHITE_CHANNEL, default=int(defaults.get(CONF_WHITE_CHANNEL, min(next_channel + 4, DMX_CHANNEL_MAX))))] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )

        if profile == PROFILE_RGBWW:
            schema[vol.Required(CONF_COLD_WHITE_CHANNEL, default=int(defaults.get(CONF_COLD_WHITE_CHANNEL, min(next_channel + 4, DMX_CHANNEL_MAX))))] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )
            schema[vol.Required(CONF_WARM_WHITE_CHANNEL, default=int(defaults.get(CONF_WARM_WHITE_CHANNEL, min(next_channel + 5, DMX_CHANNEL_MAX))))] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )

        if profile in {PROFILE_COLOR_TEMP, PROFILE_RGB_COLOR_TEMP}:
            schema[vol.Required(
                CONF_COLOR_TEMP_CHANNEL,
                default=int(
                    defaults.get(
                        CONF_COLOR_TEMP_CHANNEL,
                        min(next_channel + (4 if profile == PROFILE_RGB_COLOR_TEMP else 1), DMX_CHANNEL_MAX),
                    )
                ),
            )] = selector(
                {
                    "number": {
                        "min": DMX_CHANNEL_MIN,
                        "max": DMX_CHANNEL_MAX,
                        "mode": "box",
                        "step": 1,
                    }
                }
            )

        return vol.Schema(schema)

    def _mapping_selector_schema(self, mappings: list[dict[str, Any]]) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_MAPPING_ENTITY): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "value": mapping[CONF_ENTITY_ID],
                                    "label": mapping_label(self.hass, mapping),
                                }
                                for mapping in mappings
                            ],
                            "mode": "dropdown",
                        }
                    }
                )
            }
        )

    @staticmethod
    def _normalize_config(user_input: dict[str, Any]) -> dict[str, Any]:
        return {
            CONF_NAME: str(user_input[CONF_NAME]),
            CONF_HOST: str(user_input[CONF_HOST]),
            CONF_PORT: int(user_input[CONF_PORT]),
            CONF_UNIVERSE: int(user_input[CONF_UNIVERSE]),
            CONF_POLLING_MODE: str(user_input[CONF_POLLING_MODE]),
        }

    def _duplicate_bind_exists(
        self,
        host: str,
        port: int,
        current_entry_id: str | None = None,
    ) -> bool:
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if current_entry_id is not None and entry.entry_id == current_entry_id:
                continue
            config = config_from_entry(entry)
            if str(config[CONF_HOST]) == str(host) and int(config[CONF_PORT]) == int(port):
                return True
        return False

    def _stage_mapping_target(
        self,
        user_input: dict[str, Any],
        include_add_another: bool,
    ) -> dict[str, Any] | None:
        entity_id = str(user_input[CONF_ENTITY_ID])
        profile = preferred_profile_for_entity(self.hass, entity_id)
        if profile is None:
            return None
        staged = {
            CONF_ENTITY_ID: entity_id,
            CONF_PROFILE: profile,
        }
        if include_add_another:
            staged[CONF_ADD_ANOTHER] = bool(user_input.get(CONF_ADD_ANOTHER, False))
        return staged


class DmaixConfigFlow(BaseDmaixFlow, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._mappings: list[dict[str, Any]] = []
        self._pending_mapping: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "DmaixOptionsFlow":
        return DmaixOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            normalized = self._normalize_config(user_input)
            if self._duplicate_bind_exists(normalized[CONF_HOST], normalized[CONF_PORT]):
                errors["base"] = "already_configured"
            else:
                await self.async_set_unique_id(
                    build_unique_id(normalized[CONF_HOST], normalized[CONF_PORT])
                )
                self._config = normalized
                self._mappings = []
                self._pending_mapping = None
                return await self.async_step_mapping()

        return self.async_show_form(
            step_id="user",
            data_schema=self._config_schema(self._config),
            errors=errors,
        )

    async def async_step_mapping(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if self._pending_mapping is None:
            if user_input is not None:
                self._pending_mapping = self._stage_mapping_target(
                    user_input,
                    include_add_another=True,
                )
                if self._pending_mapping is None:
                    errors["base"] = "invalid_profile"
                    return self.async_show_form(
                        step_id="mapping",
                        data_schema=self._mapping_target_schema(include_add_another=True),
                        errors=errors,
                    )
                return self.async_show_form(
                    step_id="mapping",
                    data_schema=self._mapping_channels_schema(
                        self._pending_mapping[CONF_PROFILE],
                        self._mappings,
                    ),
                    errors={},
                )

            return self.async_show_form(
                step_id="mapping",
                data_schema=self._mapping_target_schema(include_add_another=True),
                errors={},
            )

        channel_defaults = dict(self._pending_mapping)
        if user_input is not None:
            merged_input = {
                **self._pending_mapping,
                **user_input,
            }
            channel_defaults = merged_input
            mapping = build_mapping(merged_input)
            errors = validate_mapping(self.hass, mapping, self._mappings)
            if not errors:
                add_another = bool(self._pending_mapping.get(CONF_ADD_ANOTHER, False))
                self._mappings.append(mapping)
                self._pending_mapping = None
                if add_another:
                    return await self.async_step_mapping()
                return self.async_create_entry(
                    title=self._config[CONF_NAME],
                    data={
                        **self._config,
                        CONF_MAPPINGS: self._mappings,
                    },
                )

        return self.async_show_form(
            step_id="mapping",
            data_schema=self._mapping_channels_schema(
                self._pending_mapping[CONF_PROFILE],
                self._mappings,
                defaults=channel_defaults,
            ),
            errors=errors,
        )


class DmaixOptionsFlow(BaseDmaixFlow, config_entries.OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._config = config_from_entry(config_entry)
        self._mappings = list(self._config.get(CONF_MAPPINGS, []))
        self._selected_entity_id: str | None = None
        self._pending_mapping: dict[str, Any] | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        menu_options: dict[str, str] = {
            "network": "Réseau et listener Art-Net",
            "add_mapping": "Ajouter un mapping",
            "save": "Enregistrer et recharger",
        }
        if self._mappings:
            menu_options["edit_mapping_select"] = "Modifier un mapping"
            menu_options["remove_mapping"] = "Supprimer un mapping"

        return self.async_show_menu(step_id="init", menu_options=menu_options)

    async def async_step_network(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            normalized = self._normalize_config(user_input)
            if self._duplicate_bind_exists(
                normalized[CONF_HOST],
                normalized[CONF_PORT],
                current_entry_id=self._entry.entry_id,
            ):
                errors["base"] = "already_configured"
            else:
                self._config.update(normalized)
                return await self.async_step_init()

        return self.async_show_form(
            step_id="network",
            data_schema=self._config_schema(self._config),
            errors=errors,
        )

    async def async_step_add_mapping(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if self._pending_mapping is None:
            if user_input is not None:
                self._pending_mapping = self._stage_mapping_target(
                    user_input,
                    include_add_another=True,
                )
                if self._pending_mapping is None:
                    errors["base"] = "invalid_profile"
                    return self.async_show_form(
                        step_id="add_mapping",
                        data_schema=self._mapping_target_schema(
                            defaults={CONF_ADD_ANOTHER: False},
                            include_add_another=True,
                        ),
                        errors=errors,
                    )
                return self.async_show_form(
                    step_id="add_mapping",
                    data_schema=self._mapping_channels_schema(
                        self._pending_mapping[CONF_PROFILE],
                        self._mappings,
                    ),
                    errors={},
                )

            return self.async_show_form(
                step_id="add_mapping",
                data_schema=self._mapping_target_schema(
                    defaults={CONF_ADD_ANOTHER: False},
                    include_add_another=True,
                ),
                errors={},
            )

        channel_defaults = dict(self._pending_mapping)
        if user_input is not None:
            merged_input = {
                **self._pending_mapping,
                **user_input,
            }
            channel_defaults = merged_input
            mapping = build_mapping(merged_input)
            errors = validate_mapping(self.hass, mapping, self._mappings)
            if not errors:
                add_another = bool(self._pending_mapping.get(CONF_ADD_ANOTHER, False))
                self._mappings.append(mapping)
                self._pending_mapping = None
                if add_another:
                    return await self.async_step_add_mapping()
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_mapping",
            data_schema=self._mapping_channels_schema(
                self._pending_mapping[CONF_PROFILE],
                self._mappings,
                defaults=channel_defaults,
            ),
            errors=errors,
        )

    async def async_step_edit_mapping_select(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._selected_entity_id = str(user_input[CONF_MAPPING_ENTITY])
            self._pending_mapping = None
            return await self.async_step_edit_mapping()

        return self.async_show_form(
            step_id="edit_mapping_select",
            data_schema=self._mapping_selector_schema(self._mappings),
            errors={},
        )

    async def async_step_edit_mapping(self, user_input: dict[str, Any] | None = None):
        mapping = next(
            (
                current
                for current in self._mappings
                if current[CONF_ENTITY_ID] == self._selected_entity_id
            ),
            None,
        )
        if mapping is None:
            self._pending_mapping = None
            return await self.async_step_init()

        errors: dict[str, str] = {}

        if self._pending_mapping is None:
            if user_input is not None:
                self._pending_mapping = self._stage_mapping_target(
                    user_input,
                    include_add_another=False,
                )
                if self._pending_mapping is None:
                    errors["base"] = "invalid_profile"
                    return self.async_show_form(
                        step_id="edit_mapping",
                        data_schema=self._mapping_target_schema(
                            defaults=mapping,
                            include_add_another=False,
                        ),
                        errors=errors,
                    )
                return self.async_show_form(
                    step_id="edit_mapping",
                    data_schema=self._mapping_channels_schema(
                        self._pending_mapping[CONF_PROFILE],
                        self._mappings,
                        defaults={
                            **mapping,
                            **self._pending_mapping,
                        },
                    ),
                    errors={},
                )

            return self.async_show_form(
                step_id="edit_mapping",
                data_schema=self._mapping_target_schema(
                    defaults=mapping,
                    include_add_another=False,
                ),
                errors={},
            )

        channel_defaults = {
            **mapping,
            **self._pending_mapping,
        }
        if user_input is not None:
            merged_input = {
                **self._pending_mapping,
                **user_input,
            }
            channel_defaults = {
                **mapping,
                **merged_input,
            }
            updated_mapping = build_mapping(merged_input)
            errors = validate_mapping(
                self.hass,
                updated_mapping,
                self._mappings,
                edited_entity_id=self._selected_entity_id,
            )
            if not errors:
                self._mappings = [
                    updated_mapping if current[CONF_ENTITY_ID] == self._selected_entity_id else current
                    for current in self._mappings
                ]
                self._selected_entity_id = updated_mapping[CONF_ENTITY_ID]
                self._pending_mapping = None
                return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_mapping",
            data_schema=self._mapping_channels_schema(
                self._pending_mapping[CONF_PROFILE],
                self._mappings,
                defaults=channel_defaults,
            ),
            errors=errors,
        )

    async def async_step_remove_mapping(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            selected_entity_id = str(user_input[CONF_MAPPING_ENTITY])
            self._mappings = [
                mapping
                for mapping in self._mappings
                if mapping[CONF_ENTITY_ID] != selected_entity_id
            ]
            return await self.async_step_init()

        return self.async_show_form(
            step_id="remove_mapping",
            data_schema=self._mapping_selector_schema(self._mappings),
            errors={},
        )

    async def async_step_save(self, user_input: dict[str, Any] | None = None):
        self.hass.config_entries.async_update_entry(
            self._entry,
            title=self._config[CONF_NAME],
            unique_id=build_unique_id(self._config[CONF_HOST], self._config[CONF_PORT]),
        )
        return self.async_create_entry(
            title="",
            data={
                **self._config,
                CONF_MAPPINGS: self._mappings,
            },
        )
