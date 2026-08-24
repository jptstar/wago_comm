"""Shared config-flow helpers for WAGO 750-8212 PFC200."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import WagoModbusClient
from .const import (
    CONF_COIL_SIZE,
    CONF_COIL_START,
    CONF_DISCRETE_SIZE,
    CONF_DISCRETE_START,
    CONF_HOLDING_SIZE,
    CONF_HOLDING_START,
    CONF_INPUT_SIZE,
    CONF_INPUT_START,
    CONF_RECONNECT_DELAY,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_MEMORY,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    TABLE_COIL,
    TABLE_DISCRETE,
    TABLE_HOLDING,
    TABLE_INPUT,
)


def box(minimum: float, maximum: float, step: float = 1) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=NumberSelectorMode.BOX,
        )
    )


def select(options: list[str] | dict[str, str]) -> SelectSelector:
    rendered = (
        [{"value": value, "label": label} for value, label in options.items()]
        if isinstance(options, dict)
        else options
    )
    return SelectSelector(
        SelectSelectorConfig(options=rendered, mode=SelectSelectorMode.DROPDOWN)
    )


def effective(entry: ConfigEntry, key: str, default: Any) -> Any:
    return entry.options.get(key, entry.data.get(key, default))


def memory_from_values(values: dict[str, Any]) -> dict[str, tuple[int, int]]:
    return {
        TABLE_COIL: (int(values[CONF_COIL_START]), int(values[CONF_COIL_SIZE])),
        TABLE_DISCRETE: (
            int(values[CONF_DISCRETE_START]),
            int(values[CONF_DISCRETE_SIZE]),
        ),
        TABLE_HOLDING: (
            int(values[CONF_HOLDING_START]),
            int(values[CONF_HOLDING_SIZE]),
        ),
        TABLE_INPUT: (int(values[CONF_INPUT_START]), int(values[CONF_INPUT_SIZE])),
    }


def memory_for_entry(entry: ConfigEntry) -> dict[str, tuple[int, int]]:
    values = {key: effective(entry, key, default) for key, default in DEFAULT_MEMORY.items()}
    return memory_from_values(values)


def connection_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
            vol.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
            ): box(0, 247),
            vol.Required(
                CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): box(0.5, 60, 0.5),
            vol.Required(
                CONF_RECONNECT_DELAY,
                default=defaults.get(CONF_RECONNECT_DELAY, DEFAULT_RECONNECT_DELAY),
            ): box(0, 300),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): box(1, 300),
        }
    )


def memory_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or DEFAULT_MEMORY
    fields: dict[Any, Any] = {}
    for start_key, size_key in (
        (CONF_COIL_START, CONF_COIL_SIZE),
        (CONF_DISCRETE_START, CONF_DISCRETE_SIZE),
        (CONF_HOLDING_START, CONF_HOLDING_SIZE),
        (CONF_INPUT_START, CONF_INPUT_SIZE),
    ):
        fields[
            vol.Required(start_key, default=int(defaults.get(start_key, DEFAULT_MEMORY[start_key])))
        ] = box(0, 65535)
        fields[
            vol.Required(size_key, default=int(defaults.get(size_key, DEFAULT_MEMORY[size_key])))
        ] = box(0, 65535)
    return vol.Schema(fields)


async def test_connection(data: dict[str, Any]) -> None:
    api = WagoModbusClient(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        timeout=float(data[CONF_TIMEOUT]),
        reconnect_delay=float(data[CONF_RECONNECT_DELAY]),
        unit_id=int(data[CONF_UNIT_ID]),
    )
    try:
        await api.async_connect()
    finally:
        await api.async_close()
