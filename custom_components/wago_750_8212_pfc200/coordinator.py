"""Data coordinator for WAGO 750-8212 PFC200."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WagoCommunicationError, WagoModbusClient
from .const import DOMAIN


class WagoCoordinator(DataUpdateCoordinator[dict[str, dict[int, Any]]]):
    """Poll configured Modbus blocks in grouped requests."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: WagoModbusClient,
        memory: dict[str, tuple[int, int]],
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.memory = memory

    async def _async_update_data(self) -> dict[str, dict[int, Any]]:
        try:
            return await self.api.async_read_all(self.memory)
        except WagoCommunicationError as err:
            raise UpdateFailed(str(err)) from err
