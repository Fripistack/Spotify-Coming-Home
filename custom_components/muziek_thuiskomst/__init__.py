"""Muziek Thuiskomst: Spotify gaat bij thuiskomst verder op de Sonos."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .manager import ArrivalManager

type MuziekConfigEntry = ConfigEntry[ArrivalManager]


async def async_setup_entry(hass: HomeAssistant, entry: MuziekConfigEntry) -> bool:
    """Zet één persoon op."""
    manager = ArrivalManager(hass, entry)
    entry.runtime_data = manager
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    manager.async_start()
    entry.async_on_unload(manager.async_stop)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MuziekConfigEntry) -> bool:
    """Verwijder één persoon."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: MuziekConfigEntry) -> None:
    """Herlaad na het wijzigen van de opties."""
    await hass.config_entries.async_reload(entry.entry_id)
