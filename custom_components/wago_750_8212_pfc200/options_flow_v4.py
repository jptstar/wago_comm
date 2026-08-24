"""Downloadable CSV export for WAGO Modbus."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import network

from .http import create_csv_export_token
from .options_flow_v3 import WagoOptionsFlowV3


class WagoOptionsFlowV4(WagoOptionsFlowV3):
    """Expose the point-table export as a direct browser download."""

    async def async_step_export_csv(self, user_input=None) -> ConfigFlowResult:
        """Create a simple temporary direct-download link for the CSV."""
        token = create_csv_export_token(self.hass, self._entry.entry_id)
        path = f"/wago_modbus/export/{token}.csv"
        try:
            base_url = network.get_url(self.hass)
        except network.NoURLAvailableError:
            url = path
        else:
            # An absolute URL is intentional: Home Assistant's SPA router can
            # intercept a normal click on a relative link in a Config Flow.
            url = f"{base_url.rstrip('/')}{path}"

        return self.async_abort(
            reason="export_ok",
            description_placeholders={
                "path": "prêt à télécharger",
                "url": f"[⬇ Télécharger le CSV]({url})",
            },
        )
