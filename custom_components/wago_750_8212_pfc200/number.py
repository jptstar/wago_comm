"""Number platform for configurable WAGO points."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_NUMBER
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
        if p.get("enabled", True) and p.get("platform") == PLATFORM_NUMBER
    ]
    async_add_entities(WagoNumber(runtime.coordinator, entry, point) for point in points)


class WagoNumber(WagoPointEntity, NumberEntity):
    def __init__(self, coordinator, entry, point) -> None:
        super().__init__(coordinator, entry, point)
        self._attr_native_min_value = float(point.get("min", 0.0))
        self._attr_native_max_value = float(
            point.get(
                "max",
                65535.0 * float(point.get("scale", 1.0) or 1.0),
            )
        )
        self._attr_native_step = float(point.get("step", 1.0))
        self._attr_native_unit_of_measurement = point.get("unit") or None
        if point.get("device_class"):
            try:
                self._attr_device_class = NumberDeviceClass(point["device_class"])
            except ValueError:
                pass

    @property
    def native_value(self) -> float:
        return float(self.point_value)

    async def async_set_native_value(self, value: float) -> None:
        await self.async_write_engineering(value)
