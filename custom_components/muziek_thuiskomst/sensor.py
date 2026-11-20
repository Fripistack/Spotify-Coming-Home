"""Status-sensoren: wat er bij de laatste thuiskomst gebeurde."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import STATUSES
from .entity import MuziekEntity


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback) -> None:
    manager = entry.runtime_data
    async_add_entities([StatusSensor(manager, "status"), LastTransferSensor(manager, "last_transfer")])


class StatusSensor(MuziekEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES
    _attr_icon = "mdi:music-circle"

    @property
    def native_value(self) -> str:
        return self.manager.status

    @property
    def extra_state_attributes(self) -> dict:
        return {"reden": self.manager.reason}


class LastTransferSensor(MuziekEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:speaker-wireless"

    @property
    def native_value(self):
        return self.manager.last_transfer
