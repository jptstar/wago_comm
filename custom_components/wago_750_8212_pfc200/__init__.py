"""WAGO 750-8212 PFC200 integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .api import WagoModbusClient
from .const import (
    CONF_RECONNECT_DELAY,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    NAME,
    PLATFORMS,
)
from .coordinator import WagoCoordinator
from .flow_helpers import memory_for_entry
from .http import WagoCsvExportView
from .sections import (
    section_identifier,
    section_leaf,
    section_parent,
    section_paths_from_points,
)
from .storage import async_load_points


@dataclass
class WagoRuntimeData:
    coordinator: WagoCoordinator
    points: list[dict]


type WagoConfigEntry = ConfigEntry[WagoRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-wide HTTP resources."""
    hass.http.register_view(WagoCsvExportView)
    return True


def _cleanup_removed_points_and_sections(
    hass: HomeAssistant, entry: WagoConfigEntry, points: list[dict]
) -> None:
    """Remove registry objects that no longer exist in the point table."""
    valid_unique_ids = {
        f"{entry.entry_id}_{point['id']}" for point in points if point.get("id")
    }
    entity_registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for entity in list(er.async_entries_for_config_entry(entity_registry, entry.entry_id)):
        if entity.unique_id.startswith(prefix) and entity.unique_id not in valid_unique_ids:
            entity_registry.async_remove(entity.entity_id)

    valid_section_identifiers = {
        section_identifier(entry.entry_id, path)
        for path in section_paths_from_points(points)
    }
    device_registry = dr.async_get(hass)
    for device in list(dr.async_entries_for_config_entry(device_registry, entry.entry_id)):
        section_ids = {
            identifier
            for domain, identifier in device.identifiers
            if domain == DOMAIN and identifier.startswith(f"{entry.entry_id}:")
        }
        if section_ids and section_ids.isdisjoint(valid_section_identifiers):
            device_registry.async_remove_device(device.id)


def _ensure_section_devices(
    hass: HomeAssistant, entry: WagoConfigEntry, points: list[dict]
) -> None:
    """Create used section and subsection devices with a proper hierarchy."""
    registry = dr.async_get(hass)
    for path in section_paths_from_points(points):
        parent = section_parent(path)
        via_identifier = (
            section_identifier(entry.entry_id, parent) if parent else entry.entry_id
        )
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, section_identifier(entry.entry_id, path))},
            manufacturer=MANUFACTURER,
            model=f"{NAME} — groupe Modbus",
            name=section_leaf(path),
            via_device=(DOMAIN, via_identifier),
        )


async def async_setup_entry(hass: HomeAssistant, entry: WagoConfigEntry) -> bool:
    api = WagoModbusClient(
        host=entry.data[CONF_HOST],
        port=int(entry.data[CONF_PORT]),
        timeout=float(
            entry.options.get(
                CONF_TIMEOUT, entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            )
        ),
        reconnect_delay=float(
            entry.options.get(
                CONF_RECONNECT_DELAY,
                entry.data.get(CONF_RECONNECT_DELAY, DEFAULT_RECONNECT_DELAY),
            )
        ),
        unit_id=int(
            entry.options.get(
                CONF_UNIT_ID, entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
            )
        ),
    )
    coordinator = WagoCoordinator(
        hass,
        api,
        memory_for_entry(entry),
        int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        ),
    )

    # Do not block the whole config entry if the controller is temporarily offline
    # during a Home Assistant restart. Point entities will become unavailable, while
    # the diagnostic entities remain present and "Automate en ligne" reports OFF.
    await coordinator.async_refresh()

    points = await async_load_points(hass, entry.entry_id)
    entry.runtime_data = WagoRuntimeData(coordinator=coordinator, points=points)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=entry.title,
    )

    _cleanup_removed_points_and_sections(hass, entry, points)
    _ensure_section_devices(hass, entry, points)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WagoConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.api.async_close()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: WagoConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
