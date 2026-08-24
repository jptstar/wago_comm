"""Sensor platform for configurable WAGO points and diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import PLATFORM_SENSOR
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
        if p.get("enabled", True) and p.get("platform") == PLATFORM_SENSOR
    ]
    entities: list[SensorEntity] = [
        WagoLastSuccessfulCommunication(runtime.coordinator, entry),
        WagoCommunicationDuration(runtime.coordinator, entry),
        WagoConsecutiveCommunicationFailures(runtime.coordinator, entry),
    ]
    entities.extend(WagoSensor(runtime.coordinator, entry, point) for point in points)
    async_add_entities(entities)


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


class WagoLastSuccessfulCommunication(WagoDiagnosticEntity, SensorEntity):
    """Timestamp of the last fully successful Modbus poll."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(
            coordinator,
            entry,
            "last_successful_communication",
            "Dernière communication réussie",
        )

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_successful_communication


class WagoCommunicationDuration(WagoDiagnosticEntity, SensorEntity):
    """Duration of the latest Modbus polling attempt."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:timer-outline"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator, entry) -> None:
        super().__init__(
            coordinator,
            entry,
            "communication_duration",
            "Durée de communication",
        )

    @property
    def native_value(self) -> float | None:
        return self.coordinator.last_communication_duration_ms


class WagoConsecutiveCommunicationFailures(WagoDiagnosticEntity, SensorEntity):
    """Number of consecutive failed Modbus polling cycles."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(
            coordinator,
            entry,
            "consecutive_communication_failures",
            "Échecs de communication consécutifs",
        )

    @property
    def native_value(self) -> int:
        return self.coordinator.consecutive_communication_failures
