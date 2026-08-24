"""Button platform for configurable WAGO points."""

from __future__ import annotations

import asyncio

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_BUTTON
from .entity import WagoPointEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime = entry.runtime_data
    points = [p for p in runtime.points if p.get("enabled", True) and p.get("platform") == PLATFORM_BUTTON]
    async_add_entities(WagoButton(runtime.coordinator, entry, point) for point in points)


class WagoButton(WagoPointEntity, ButtonEntity):
    async def async_press(self) -> None:
        active = self.point.get("active_value", 1)
        await self.async_write_raw(active)
        if self.point.get("command_mode", "pulse") == "pulse":
            await asyncio.sleep(max(0, int(self.point.get("pulse_ms", 300))) / 1000)
            await self.async_write_raw(self.point.get("return_value", 0))
