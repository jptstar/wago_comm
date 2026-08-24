"""Shared entity helpers."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL, NAME, TABLE_COIL, TABLE_HOLDING
from .coordinator import WagoCoordinator
from .point import (
    decoded_point_value,
    encode_engineering_value,
    encode_raw_value,
    raw_point_value,
)
from .sections import (
    normalize_section_path,
    section_identifier,
    section_leaf,
    section_parent,
)


class WagoPointEntity(CoordinatorEntity[WagoCoordinator]):
    """Base class for a configurable WAGO point."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WagoCoordinator,
        entry: ConfigEntry,
        point: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.point = point
        point_id = str(point["id"])
        self._attr_unique_id = f"{entry.entry_id}_{point_id}"
        self._attr_name = str(point.get("name") or point_id)
        self._attr_icon = point.get("icon") or None

    @property
    def device_info(self) -> DeviceInfo:
        section = normalize_section_path(self.point.get("section", ""))
        if not section:
            return DeviceInfo(
                identifiers={(DOMAIN, self.entry.entry_id)},
                name=self.entry.title,
                manufacturer=MANUFACTURER,
                model=MODEL,
            )
        parent = section_parent(section)
        via_identifier = (
            section_identifier(self.entry.entry_id, parent)
            if parent
            else self.entry.entry_id
        )
        return DeviceInfo(
            identifiers={(DOMAIN, section_identifier(self.entry.entry_id, section))},
            name=section_leaf(section),
            manufacturer=MANUFACTURER,
            model=f"{NAME} — groupe Modbus",
            via_device=(DOMAIN, via_identifier),
        )

    @property
    def point_value(self) -> Any:
        return decoded_point_value(self.coordinator.data or {}, self.point)

    @property
    def raw_value(self) -> Any:
        return raw_point_value(self.coordinator.data or {}, self.point)

    async def async_write_engineering(self, value: float) -> None:
        table = self.point["table"]
        address = int(self.point["address"])
        if table == TABLE_COIL:
            await self.coordinator.api.async_write_coil(address, bool(value))
        elif table == TABLE_HOLDING:
            bit = self.point.get("bit")
            if bit is not None:
                current = int(
                    (self.coordinator.data or {})
                    .get(TABLE_HOLDING, {})
                    .get(address, 0)
                )
                mask = 1 << int(bit)
                raw_bool = bool(value)
                if self.point.get("inverted", False):
                    raw_bool = not raw_bool
                new_value = current | mask if raw_bool else current & ~mask
                await self.coordinator.api.async_write_registers(address, [new_value])
            else:
                await self.coordinator.api.async_write_registers(
                    address, encode_engineering_value(value, self.point)
                )
        else:
            raise ValueError(f"Table {table} is read-only")
        if self.point.get("read_after_write", True):
            await self.coordinator.async_request_refresh()

    async def async_write_raw(self, value: int | float | bool) -> None:
        table = self.point["table"]
        address = int(self.point["address"])
        if table == TABLE_COIL:
            raw_bool = bool(value)
            if self.point.get("inverted", False):
                raw_bool = not raw_bool
            await self.coordinator.api.async_write_coil(address, raw_bool)
        elif table == TABLE_HOLDING:
            bit = self.point.get("bit")
            if bit is not None:
                current = int(
                    (self.coordinator.data or {})
                    .get(TABLE_HOLDING, {})
                    .get(address, 0)
                )
                mask = 1 << int(bit)
                raw_bool = bool(value)
                if self.point.get("inverted", False):
                    raw_bool = not raw_bool
                new_value = current | mask if raw_bool else current & ~mask
                await self.coordinator.api.async_write_registers(address, [new_value])
            else:
                await self.coordinator.api.async_write_registers(
                    address, encode_raw_value(value, self.point)
                )
        else:
            raise ValueError(f"Table {table} is read-only")
        if self.point.get("read_after_write", True):
            await self.coordinator.async_request_refresh()
