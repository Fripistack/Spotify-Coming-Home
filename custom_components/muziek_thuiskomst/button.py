"""Knop: muziek nu meteen naar de speakers."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MuziekEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([TransferButton(entry.runtime_data, "transfer_now")])


class TransferButton(MuziekEntity, ButtonEntity):
    _attr_icon = "mdi:speaker-play"

    async def async_press(self) -> None:
        await self.manager.async_transfer("knop")
