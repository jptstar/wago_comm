"""Downloadable CSV export for WAGO Modbus."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN
from .options_flow_v3 import WagoOptionsFlowV3


class WagoOptionsFlowV4(WagoOptionsFlowV3):
    """Expose the point-table export as an authenticated download."""

    async def async_step_export_csv(self, user_input=None) -> ConfigFlowResult:
        """Return a direct download link instead of writing into /config/www."""
        url = f"/api/{DOMAIN}/export/{self._entry.entry_id}.csv"
        return self.async_abort(
            reason="export_ready",
            description_placeholders={"url": url},
        )
