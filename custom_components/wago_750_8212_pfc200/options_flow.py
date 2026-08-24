"""Options flow for WAGO 750-8212 PFC200."""

from __future__ import annotations

import csv
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_TIMEOUT
from homeassistant.helpers.selector import FileSelector, FileSelectorConfig

from .const import (
    CONF_POINTS_REVISION,
    CONF_RECONNECT_DELAY,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_MEMORY,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    TABLE_COIL,
    TABLE_DISCRETE,
    TABLE_HOLDING,
    TABLE_INPUT,
)
from .csv_io import export_csv_text, parse_csv_text, validate_points
from .flow_helpers import box, effective, memory_for_entry, memory_from_values, memory_schema, select
from .point_options import WagoPointOptionsMixin
from .sections import normalize_section_path
from .storage import async_load_points, async_save_points


class WagoOptionsFlow(WagoPointOptionsMixin, config_entries.OptionsFlow):
    """Manage communication, memory and point definitions."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._selected_point_id: str | None = None
        self._point_action: str | None = None
        self._point_draft: dict[str, Any] = {}
        self._point_original: dict[str, Any] = {}
        self._import_points: list[dict[str, Any]] = []
        self._import_warnings: list[str] = []
        self._import_mode = "replace"

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["communication", "memory", "points", "import_csv", "export_csv"],
        )

    async def async_step_communication(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            data = dict(self._entry.options)
            data.update(user_input)
            return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="communication",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UNIT_ID, default=effective(self._entry, CONF_UNIT_ID, DEFAULT_UNIT_ID)
                    ): box(0, 247),
                    vol.Required(
                        CONF_TIMEOUT, default=effective(self._entry, CONF_TIMEOUT, DEFAULT_TIMEOUT)
                    ): box(0.5, 60, 0.5),
                    vol.Required(
                        CONF_RECONNECT_DELAY,
                        default=effective(
                            self._entry, CONF_RECONNECT_DELAY, DEFAULT_RECONNECT_DELAY
                        ),
                    ): box(0, 300),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=effective(self._entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): box(1, 300),
                }
            ),
        )

    async def async_step_memory(self, user_input=None) -> ConfigFlowResult:
        defaults = {
            key: effective(self._entry, key, default) for key, default in DEFAULT_MEMORY.items()
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            points = await async_load_points(self.hass, self._entry.entry_id)
            point_errors, _ = validate_points(points, memory_from_values(user_input))
            if point_errors:
                errors["base"] = "memory_conflict"
            else:
                data = dict(self._entry.options)
                data.update(user_input)
                return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="memory", data_schema=memory_schema(defaults), errors=errors
        )

    def _finish_points_change(self) -> ConfigFlowResult:
        data = dict(self._entry.options)
        data[CONF_POINTS_REVISION] = int(data.get(CONF_POINTS_REVISION, 0)) + 1
        return self.async_create_entry(title="", data=data)

    def _read_uploaded_csv(self, upload_id: str) -> str:
        with process_uploaded_file(self.hass, upload_id) as file_path:
            return file_path.read_text(encoding="utf-8-sig")

    async def async_step_import_csv(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"details": ""}
        if user_input is not None:
            try:
                text = await self.hass.async_add_executor_job(
                    self._read_uploaded_csv, user_input["file"]
                )
                points, parse_errors, warnings = parse_csv_text(
                    text, memory_for_entry(self._entry)
                )
            except (OSError, UnicodeError, csv.Error, ValueError):
                errors["base"] = "invalid_csv"
            else:
                if parse_errors:
                    errors["base"] = "invalid_csv"
                    placeholders["details"] = "\n".join(parse_errors[:10])
                else:
                    for point in points:
                        point["section"] = normalize_section_path(point.get("section", ""))
                    self._import_points = points
                    self._import_warnings = warnings
                    self._import_mode = user_input["mode"]
                    return await self.async_step_import_confirm()
        return self.async_show_form(
            step_id="import_csv",
            data_schema=vol.Schema(
                {
                    vol.Required("file"): FileSelector(
                        FileSelectorConfig(accept=".csv,text/csv,text/plain")
                    ),
                    vol.Required("mode", default="replace"): select(
                        {"replace": "Remplacer la table", "merge": "Fusionner par ID"}
                    ),
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_export_csv(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            if not user_input.get("confirm"):
                return self.async_show_form(
                    step_id="export_csv",
                    data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
                    errors={"base": "confirmation_required"},
                )
            points = await async_load_points(self.hass, self._entry.entry_id)
            text = export_csv_text(points)
            export_dir = self.hass.config.path("www", "wago_exports")
            export_path = self.hass.config.path(
                "www", "wago_exports", f"{self._entry.entry_id}_points.csv"
            )

            def _write_export() -> None:
                import os

                os.makedirs(export_dir, exist_ok=True)
                with open(export_path, "w", encoding="utf-8-sig", newline="") as handle:
                    handle.write(text)

            await self.hass.async_add_executor_job(_write_export)
            return self.async_abort(
                reason="export_ok",
                description_placeholders={
                    "path": export_path,
                    "url": f"/local/wago_exports/{self._entry.entry_id}_points.csv",
                },
            )
        return self.async_show_form(
            step_id="export_csv",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )

    async def async_step_import_confirm(self, user_input=None) -> ConfigFlowResult:
        current = await async_load_points(self.hass, self._entry.entry_id)
        if self._import_mode == "merge":
            merged = {p["id"]: p for p in current}
            merged.update({p["id"]: p for p in self._import_points})
            final = list(merged.values())
        else:
            final = list(self._import_points)
        errors, warnings = validate_points(final, memory_for_entry(self._entry))
        if errors:
            return self.async_abort(reason="invalid_csv")
        if user_input is not None:
            if not user_input.get("confirm"):
                return self.async_show_form(
                    step_id="import_confirm",
                    data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
                    errors={"base": "confirmation_required"},
                )
            await async_save_points(self.hass, self._entry.entry_id, final)
            return self._finish_points_change()
        counts: dict[str, int] = {}
        for point in final:
            counts[point["table"]] = counts.get(point["table"], 0) + 1
        summary = (
            f"{len(final)} points après import — coils {counts.get(TABLE_COIL, 0)}, "
            f"DI {counts.get(TABLE_DISCRETE, 0)}, HR {counts.get(TABLE_HOLDING, 0)}, "
            f"IR {counts.get(TABLE_INPUT, 0)}"
        )
        details = "\n".join((self._import_warnings + warnings)[:10]) or "Aucun avertissement"
        return self.async_show_form(
            step_id="import_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"summary": summary, "details": details},
        )
