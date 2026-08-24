"""Switch platform for configurable WAGO points."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_SWITCH
from .entity import WagoPointEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime = entry.runtime_data
    points = [p for p in runtime.points if p.get("enabled", True) and p.get("platform") == PLATFORM_SWITCH]
    async_add_entities(WagoSwitch(runtime.coordinator, entry, point) for point in points)


class WagoSwitch(WagoPointEntity, SwitchEntity):
    @property
    def is_on(self) -> bool:
        return bool(self.point_value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.async_write_raw(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.async_write_raw(False)
