"""Binary sensor platform for configurable WAGO points."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_BINARY_SENSOR
from .entity import WagoPointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    points = [
        p
        for p in runtime.points
        if p.get("enabled", True) and p.get("platform") == PLATFORM_BINARY_SENSOR
    ]
    async_add_entities(
        WagoBinarySensor(runtime.coordinator, entry, point) for point in points
    )


class WagoBinarySensor(WagoPointEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry, point) -> None:
        super().__init__(coordinator, entry, point)
        if point.get("device_class"):
            try:
                self._attr_device_class = BinarySensorDeviceClass(point["device_class"])
            except ValueError:
                pass

    @property
    def is_on(self) -> bool:
        return bool(self.point_value)
