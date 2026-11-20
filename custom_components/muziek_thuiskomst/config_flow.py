"""Instellen via de UI: persoon, speakers en logica."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_BT_SENSOR,
    CONF_BT_TIMEOUT,
    CONF_CAR_NAME,
    CONF_END,
    CONF_FALLBACK,
    CONF_ONLY_ALONE,
    CONF_PAUSE_MARGIN,
    CONF_PERSON,
    CONF_SET_VOLUME,
    CONF_SOURCE,
    CONF_SPEAKERS,
    CONF_SPOTIFY,
    CONF_START,
    CONF_VOLUME,
    DEFAULTS,
    DOMAIN,
)


def _person_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_PERSON, default=defaults.get(CONF_PERSON, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="person")
            ),
            vol.Required(CONF_SPOTIFY, default=defaults.get(CONF_SPOTIFY, vol.UNDEFINED)): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player", integration="spotify")
            ),
        }
    )


def _speakers_schema(hass: HomeAssistant, cfg: dict[str, Any]) -> vol.Schema:
    spotify = hass.states.get(cfg.get(CONF_SPOTIFY, ""))
    sources = list(spotify.attributes.get("source_list") or []) if spotify else []
    current = cfg.get(CONF_SOURCE) or ""
    if current and current not in sources:
        sources.append(current)
    return vol.Schema(
        {
            vol.Required(CONF_SPEAKERS, default=cfg.get(CONF_SPEAKERS, [])): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="media_player", multiple=True)
            ),
            vol.Optional(CONF_SOURCE, description={"suggested_value": current}): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=sources,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_SET_VOLUME, default=cfg[CONF_SET_VOLUME]): selector.BooleanSelector(),
            vol.Required(CONF_VOLUME, default=cfg[CONF_VOLUME]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=100, step=1, unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(CONF_FALLBACK, default=cfg[CONF_FALLBACK]): selector.BooleanSelector(),
        }
    )


def _logic_schema(cfg: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ONLY_ALONE, default=cfg[CONF_ONLY_ALONE]): selector.BooleanSelector(),
            vol.Required(CONF_START, default=cfg[CONF_START]): selector.TimeSelector(),
            vol.Required(CONF_END, default=cfg[CONF_END]): selector.TimeSelector(),
            vol.Required(CONF_PAUSE_MARGIN, default=cfg[CONF_PAUSE_MARGIN]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=60, step=1, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(CONF_BT_SENSOR, description={"suggested_value": cfg.get(CONF_BT_SENSOR) or None}): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(CONF_CAR_NAME, description={"suggested_value": cfg.get(CONF_CAR_NAME) or None}): selector.TextSelector(),
            vol.Required(CONF_BT_TIMEOUT, default=cfg[CONF_BT_TIMEOUT]): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=60, step=1, unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _clean_speakers(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    data = dict(user_input)
    data[CONF_SOURCE] = (data.get(CONF_SOURCE) or "").strip()
    data[CONF_VOLUME] = int(data[CONF_VOLUME])
    errors: dict[str, str] = {}
    if not data.get(CONF_SPEAKERS):
        errors[CONF_SPEAKERS] = "no_speakers"
    return data, errors


def _clean_logic(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    data = dict(user_input)
    data[CONF_BT_SENSOR] = data.get(CONF_BT_SENSOR) or ""
    data[CONF_CAR_NAME] = (data.get(CONF_CAR_NAME) or "").strip()
    data[CONF_PAUSE_MARGIN] = int(data[CONF_PAUSE_MARGIN])
    data[CONF_BT_TIMEOUT] = int(data[CONF_BT_TIMEOUT])
    errors: dict[str, str] = {}
    if data[CONF_BT_SENSOR] and not data[CONF_CAR_NAME]:
        errors[CONF_CAR_NAME] = "car_name_required"
    return data, errors


class MuziekThuiskomstConfigFlow(ConfigFlow, domain=DOMAIN):
    """Nieuwe persoon toevoegen."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_PERSON])
            self._abort_if_unique_id_configured()
            self._data.update(user_input)
            return await self.async_step_speakers()
        return self.async_show_form(step_id="user", data_schema=_person_schema({}))

    async def async_step_speakers(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _clean_speakers(user_input)
            if not errors:
                self._data.update(data)
                return await self.async_step_logic()
        return self.async_show_form(
            step_id="speakers",
            data_schema=_speakers_schema(self.hass, self._data),
            errors=errors,
        )

    async def async_step_logic(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _clean_logic(user_input)
            if not errors:
                self._data.update(data)
                person = self.hass.states.get(self._data[CONF_PERSON])
                title = person.name if person else self._data[CONF_PERSON]
                return self.async_create_entry(title=title, data=self._data)
        return self.async_show_form(
            step_id="logic", data_schema=_logic_schema(self._data), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MuziekThuiskomstOptionsFlow()


class MuziekThuiskomstOptionsFlow(OptionsFlow):
    """Speakers en logica later aanpassen."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def _cfg(self) -> dict[str, Any]:
        return {**DEFAULTS, **self.config_entry.data, **self.config_entry.options, **self._data}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["speakers", "logic", "spotify"])

    async def async_step_spotify(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        cfg = self._cfg()
        if user_input is not None:
            return self.async_create_entry(data={**self.config_entry.options, CONF_SPOTIFY: user_input[CONF_SPOTIFY]})
        schema = vol.Schema(
            {
                vol.Required(CONF_SPOTIFY, default=cfg[CONF_SPOTIFY]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="media_player", integration="spotify")
                )
            }
        )
        return self.async_show_form(step_id="spotify", data_schema=schema)

    async def async_step_speakers(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _clean_speakers(user_input)
            if not errors:
                return self.async_create_entry(data={**self.config_entry.options, **data})
        return self.async_show_form(
            step_id="speakers",
            data_schema=_speakers_schema(self.hass, self._cfg()),
            errors=errors,
        )

    async def async_step_logic(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _clean_logic(user_input)
            if not errors:
                return self.async_create_entry(data={**self.config_entry.options, **data})
        return self.async_show_form(
            step_id="logic", data_schema=_logic_schema(self._cfg()), errors=errors
        )
