"""Config flow for WAGO 750-8212 PFC200."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import callback

from .api import WagoCommunicationError
from .const import (
    CONF_RECONNECT_DELAY,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    DOMAIN,
)
from .flow_helpers import connection_schema, effective, memory_for_entry, memory_schema, test_connection
from .options_flow import WagoOptionsFlow

# Kept as a public helper for the integration runtime.
_memory_for_entry = memory_for_entry


class WagoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a WAGO controller."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await test_connection(user_input)
            except (WagoCommunicationError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                self._connection = dict(user_input)
                return await self.async_step_memory()
        return self.async_show_form(
            step_id="user", data_schema=connection_schema(user_input), errors=errors
        )

    async def async_step_memory(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            data = {**self._connection, **user_input}
            unique_id = f"{data[CONF_HOST]}:{data[CONF_PORT]}:{int(data[CONF_UNIT_ID])}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"WAGO PFC200 {data[CONF_HOST]}", data=data
            )
        return self.async_show_form(step_id="memory", data_schema=memory_schema())

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        defaults = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data[CONF_PORT],
            CONF_UNIT_ID: effective(entry, CONF_UNIT_ID, DEFAULT_UNIT_ID),
            CONF_TIMEOUT: effective(entry, CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_RECONNECT_DELAY: effective(
                entry, CONF_RECONNECT_DELAY, DEFAULT_RECONNECT_DELAY
            ),
            CONF_SCAN_INTERVAL: effective(
                entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        }
        if user_input is not None:
            try:
                await test_connection(user_input)
            except (WagoCommunicationError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                new_data = dict(entry.data)
                new_data.update(user_input)
                unique_id = (
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:"
                    f"{int(user_input[CONF_UNIT_ID])}"
                )
                existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, unique_id
                )
                if existing is not None and existing.entry_id != entry.entry_id:
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                    unique_id=unique_id,
                    title=f"WAGO PFC200 {user_input[CONF_HOST]}",
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=connection_schema(defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return WagoOptionsFlow(config_entry)
