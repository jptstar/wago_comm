"""Number platform for configurable WAGO points."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_NUMBER, TABLE_COIL
from .entity import WagoPointEntity

_APPLY_RELATIONS = {
    # WAGO/CODESYS profile: writing HR64 changes the threshold value, then
    # mSet_PressionDifferentiel (Coil 6) must be pulsed to apply it.
    "filter_pressure_delta_threshold": "filter_pressure_delta_command",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    by_id = {str(point.get("id")): point for point in runtime.points}
    points = [
        p
        for p in runtime.points
        if p.get("enabled", True) and p.get("platform") == PLATFORM_NUMBER
    ]
    async_add_entities(
        WagoNumber(
            runtime.coordinator,
            entry,
            point,
            by_id.get(_APPLY_RELATIONS.get(str(point.get("id")), "")),
        )
        for point in points
    )


class WagoNumber(WagoPointEntity, NumberEntity):
    def __init__(
        self,
        coordinator,
        entry,
        point: dict[str, Any],
        apply_point: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(coordinator, entry, point)
        self._apply_point = apply_point
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
        """Write a number and run its optional profile apply command."""
        await self.async_write_engineering(value)

        apply_point = self._apply_point
        if not apply_point or not apply_point.get("enabled", True):
            return
        if apply_point.get("table") != TABLE_COIL:
            return

        address = int(apply_point["address"])
        active = bool(apply_point.get("active_value", 1))
        return_value = bool(apply_point.get("return_value", 0))
        if apply_point.get("inverted", False):
            active = not active
            return_value = not return_value

        await self.coordinator.api.async_write_coil(address, active)
        if apply_point.get("command_mode", "pulse") == "pulse":
            await asyncio.sleep(
                max(0, int(apply_point.get("pulse_ms", 300))) / 1000
            )
            await self.coordinator.api.async_write_coil(address, return_value)

        await self.coordinator.async_request_refresh()
