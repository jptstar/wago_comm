"""Binary sensor platform for configurable WAGO points and diagnostics."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_BINARY_SENSOR
from .entity import WagoDiagnosticEntity, WagoPointEntity


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
    entities: list[BinarySensorEntity] = [
        WagoControllerOnline(runtime.coordinator, entry)
    ]
    entities.extend(
        WagoBinarySensor(runtime.coordinator, entry, point) for point in points
    )
    async_add_entities(entities)


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


class WagoControllerOnline(WagoDiagnosticEntity, BinarySensorEntity):
    """Connectivity state derived from the latest Modbus polling cycle."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(
            coordinator,
            entry,
            "controller_online",
            "Automate en ligne",
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.controller_online
