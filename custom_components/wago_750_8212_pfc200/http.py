"""HTTP endpoints for WAGO Modbus."""

from __future__ import annotations

import re

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .csv_io import export_csv_text
from .storage import async_load_points


def _safe_filename(value: str) -> str:
    """Return a filesystem/browser-safe filename component."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._-") or "wago"


class WagoCsvExportView(HomeAssistantView):
    """Download the current point table as a CSV attachment."""

    url = f"/api/{DOMAIN}/export/{{entry_id}}.csv"
    name = f"api:{DOMAIN}:export_csv"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Generate and return the CSV for one WAGO config entry."""
        hass: HomeAssistant = request.app["hass"]
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise web.HTTPNotFound()

        points = await async_load_points(hass, entry_id)
        text = export_csv_text(points)
        host = _safe_filename(str(entry.data.get(CONF_HOST, "wago")))
        filename = f"wago_modbus_{host}_points.csv"

        return web.Response(
            body=text.encode("utf-8-sig"),
            content_type="text/csv",
            charset="utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
