"""Binary sensor platform for configurable WAGO points."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_BINARY_SENSOR
from .entity import WagoPointEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime = entry.runtime_data
    points = [p for p in runtime.points if p.get("enabled", True) and p.get("platform") == PLATFORM_BINARY_SENSOR]
    async_add_entities(WagoBinarySensor(runtime.coordinator, entry, point) for point in points)


class WagoBinarySensor(WagoPointEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool:
        return bool(self.point_value)
