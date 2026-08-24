"""HTTP endpoints for WAGO Modbus."""

from __future__ import annotations

import re
import secrets
import time
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .csv_io import export_csv_text
from .storage import async_load_points

_EXPORT_TOKENS = "csv_export_tokens"
_EXPORT_TOKEN_TTL = 600.0


def _safe_filename(value: str) -> str:
    """Return a filesystem/browser-safe filename component."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._-") or "wago"


def _token_store(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """Return the temporary CSV export token store."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    return domain_data.setdefault(_EXPORT_TOKENS, {})


def create_csv_export_token(hass: HomeAssistant, entry_id: str) -> str:
    """Create an unguessable temporary CSV download token."""
    store = _token_store(hass)
    now = time.monotonic()

    for old_token, data in list(store.items()):
        if float(data.get("expires", 0)) <= now:
            store.pop(old_token, None)

    token = secrets.token_urlsafe(32)
    store[token] = {
        "entry_id": entry_id,
        "expires": now + _EXPORT_TOKEN_TTL,
    }
    return token


class WagoCsvExportView(HomeAssistantView):
    """Download the current point table as a CSV attachment."""

    # Deliberately outside /api/. A relative /api link shown by a Config Flow can
    # be intercepted by Home Assistant's SPA router on a normal click/tap.
    url = f"/wago_modbus/export/{{token}}.csv"
    name = f"api:{DOMAIN}:export_csv"
    requires_auth = False

    async def get(self, request: web.Request, token: str) -> web.Response:
        """Generate and return one CSV export."""
        hass: HomeAssistant = request.app["hass"]
        store = _token_store(hass)
        data = store.get(token)
        if data is None:
            raise web.HTTPNotFound()

        if float(data.get("expires", 0)) <= time.monotonic():
            store.pop(token, None)
            raise web.HTTPGone(text="Ce lien d’export CSV a expiré.")

        entry_id = str(data.get("entry_id", ""))
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
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "X-Content-Type-Options": "nosniff",
            },
        )
