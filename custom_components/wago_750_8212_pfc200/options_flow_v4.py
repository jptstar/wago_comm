"""Downloadable CSV export for WAGO Modbus."""

from __future__ import annotations

from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN
from .http import create_csv_export_token
from .options_flow_v3 import WagoOptionsFlowV3


class WagoOptionsFlowV4(WagoOptionsFlowV3):
    """Expose the point-table export as a direct browser download."""

    async def async_step_export_csv(self, user_input=None) -> ConfigFlowResult:
        """Create a short-lived single-use download link for the CSV."""
        token = create_csv_export_token(self.hass, self._entry.entry_id)
        url = f"/api/{DOMAIN}/export/{token}.csv"
        return self.async_abort(
            reason="export_ok",
            description_placeholders={
                "path": "lien valable 5 minutes et utilisable une seule fois",
                "url": f"[Télécharger le CSV maintenant]({url})",
            },
        )
