"""Data coordinator for WAGO 750-8212 PFC200."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from time import monotonic
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
        self.last_successful_communication: datetime | None = None
        self.last_communication_duration_ms: float | None = None
        self.consecutive_communication_failures = 0

    @property
    def controller_online(self) -> bool:
        """Return whether the last Modbus polling cycle completed successfully."""
        return bool(self.last_update_success and self.last_successful_communication is not None)

    async def _async_update_data(self) -> dict[str, dict[int, Any]]:
        started = monotonic()
        try:
            data = await self.api.async_read_all(self.memory)
        except WagoCommunicationError as err:
            self.last_communication_duration_ms = round(
                (monotonic() - started) * 1000.0, 1
            )
            self.consecutive_communication_failures += 1
            raise UpdateFailed(str(err)) from err

        self.last_communication_duration_ms = round(
            (monotonic() - started) * 1000.0, 1
        )
        self.last_successful_communication = datetime.now(timezone.utc)
        self.consecutive_communication_failures = 0
        return data
