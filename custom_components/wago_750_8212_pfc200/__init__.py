"""WAGO 750-8212 PFC200 integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .api import WagoCommunicationError, WagoModbusClient
from .config_flow import _memory_for_entry
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
    PLATFORMS,
)
from .coordinator import WagoCoordinator
from .storage import async_load_points


@dataclass
class WagoRuntimeData:
    coordinator: WagoCoordinator
    points: list[dict]


type WagoConfigEntry = ConfigEntry[WagoRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


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
        _memory_for_entry(entry),
        int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        ),
    )
    try:
        await api.async_connect()
        await coordinator.async_config_entry_first_refresh()
    except (WagoCommunicationError, OSError) as err:
        await api.async_close()
        raise ConfigEntryNotReady(str(err)) from err

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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WagoConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.api.async_close()
    return unloaded


async def _async_reload_entry(
    hass: HomeAssistant, entry: WagoConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
