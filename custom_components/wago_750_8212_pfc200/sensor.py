"""Sensor platform for configurable WAGO points."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_SENSOR
from .entity import WagoPointEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    points = [p for p in runtime.points if p.get("enabled", True) and p.get("platform") == PLATFORM_SENSOR]
    async_add_entities(WagoSensor(runtime.coordinator, entry, point) for point in points)


class WagoSensor(WagoPointEntity, SensorEntity):
    def __init__(self, coordinator, entry, point: dict[str, Any]) -> None:
        super().__init__(coordinator, entry, point)
        self._attr_native_unit_of_measurement = point.get("unit") or None
        self._attr_suggested_display_precision = point.get("precision")
        if point.get("device_class"):
            try:
                self._attr_device_class = SensorDeviceClass(point["device_class"])
            except ValueError:
                pass
        if point.get("state_class"):
            try:
                self._attr_state_class = SensorStateClass(point["state_class"])
            except ValueError:
                pass

    @property
    def native_value(self):
        return self.point_value
