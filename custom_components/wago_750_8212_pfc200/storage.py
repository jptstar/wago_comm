"""Persistent point storage for WAGO 750-8212 PFC200."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY_PREFIX, STORAGE_VERSION


def _store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}")


async def async_load_points(hass: HomeAssistant, entry_id: str) -> list[dict[str, Any]]:
    data = await _store(hass, entry_id).async_load()
    if not isinstance(data, dict):
        return []
    points = data.get("points", [])
    return [dict(point) for point in points if isinstance(point, dict)]


async def async_save_points(
    hass: HomeAssistant, entry_id: str, points: list[dict[str, Any]]
) -> None:
    await _store(hass, entry_id).async_save({"points": points})
