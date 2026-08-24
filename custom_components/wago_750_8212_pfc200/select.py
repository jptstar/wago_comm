"""Select platform for configurable WAGO points."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_SELECT
from .entity import WagoPointEntity
from .point import parse_select_options


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime = entry.runtime_data
    points = [p for p in runtime.points if p.get("enabled", True) and p.get("platform") == PLATFORM_SELECT]
    async_add_entities(WagoSelect(runtime.coordinator, entry, point) for point in points)


class WagoSelect(WagoPointEntity, SelectEntity):
    def __init__(self, coordinator, entry, point) -> None:
        super().__init__(coordinator, entry, point)
        self.mapping = parse_select_options(point.get("select_options"))
        self.reverse = {label: raw for raw, label in self.mapping.items()}
        self._attr_options = list(self.reverse)

    @property
    def current_option(self) -> str | None:
        raw = int(self.raw_value)
        return self.mapping.get(raw, f"Inconnu ({raw})")

    async def async_select_option(self, option: str) -> None:
        if option not in self.reverse:
            raise ValueError(f"Unknown option: {option}")
        await self.async_write_raw(self.reverse[option])
