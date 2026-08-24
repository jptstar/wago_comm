"""Dynamic point editor used by the WAGO options flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    DATA_BOOL,
    DATA_TYPES,
    DATA_UINT16,
    MAX_POINTS,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_BUTTON,
    PLATFORM_NUMBER,
    PLATFORM_SELECT,
    PLATFORM_SENSOR,
    PLATFORM_SWITCH,
    TABLE_COIL,
    TABLE_DISCRETE,
    TABLE_HOLDING,
    TABLE_INPUT,
)
from .csv_io import validate_points
from .flow_helpers import box, memory_for_entry, select
from .point import register_count, slugify
from .sections import normalize_section_path, section_paths_from_points
from .storage import async_load_points, async_save_points

SECTION_ROOT = "__root__"
SECTION_NEW = "__new__"

PLATFORM_LABELS = {
    PLATFORM_SENSOR: "Capteur",
    PLATFORM_BINARY_SENSOR: "Capteur binaire",
    PLATFORM_SWITCH: "Interrupteur",
    PLATFORM_NUMBER: "Nombre",
    PLATFORM_BUTTON: "Bouton",
    PLATFORM_SELECT: "Liste de sélection",
}

TABLE_LABELS = {
    TABLE_COIL: "Coil",
    TABLE_DISCRETE: "Discrete Input",
    TABLE_HOLDING: "Holding Register",
    TABLE_INPUT: "Input Register",
}

WRITABLE_PLATFORMS = {
    PLATFORM_SWITCH,
    PLATFORM_NUMBER,
    PLATFORM_BUTTON,
    PLATFORM_SELECT,
}


class WagoPointOptionsMixin:
    """Wizard that only exposes fields relevant to the selected entity type."""

    async def async_step_points(self, user_input=None) -> ConfigFlowResult:
        points = await async_load_points(self.hass, self._entry.entry_id)
        if user_input is not None:
            action = user_input["action"]
            self._point_action = action
            self._selected_point_id = user_input.get("point_id") or None
            self._point_draft = {}
            self._point_original = {}
            if action == "add":
                return await self.async_step_point_form()
            if not self._selected_point_id:
                return self.async_show_form(
                    step_id="points",
                    data_schema=self._points_schema(points),
                    errors={"base": "point_required"},
                )
            if action in ("edit", "duplicate"):
                return await self.async_step_point_form()
            if action == "delete":
                return await self.async_step_delete_point()
        return self.async_show_form(
            step_id="points", data_schema=self._points_schema(points)
        )

    def _points_schema(self, points: list[dict[str, Any]]) -> vol.Schema:
        point_options = [
            {
                "value": p["id"],
                "label": (
                    f"{p.get('section', '')} — {p.get('name', p['id'])} "
                    f"[{p.get('table')} {p.get('address')}]"
                ).lstrip(" —"),
            }
            for p in points
        ]
        fields: dict[Any, Any] = {
            vol.Required("action", default="add"): select(
                {
                    "add": "Ajouter",
                    "edit": "Modifier",
                    "duplicate": "Dupliquer",
                    "delete": "Supprimer",
                }
            )
        }
        if point_options:
            fields[vol.Optional("point_id")] = SelectSelector(
                SelectSelectorConfig(
                    options=point_options, mode=SelectSelectorMode.DROPDOWN
                )
            )
        return vol.Schema(fields)

    async def _prepare_point_defaults(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        points = await async_load_points(self.hass, self._entry.entry_id)
        original = next(
            (p for p in points if p.get("id") == self._selected_point_id), {}
        )
        self._point_original = dict(original)
        defaults = dict(original)
        if self._point_action == "duplicate" and defaults:
            defaults["id"] = f"{defaults['id']}_copy"
            defaults["name"] = f"{defaults.get('name', defaults['id'])} copie"
        return points, defaults

    def _section_selector(self, points: list[dict[str, Any]], current: str) -> SelectSelector:
        paths = section_paths_from_points(points)
        current = normalize_section_path(current)
        if current and current not in paths:
            paths.append(current)
        options = [
            {"value": SECTION_ROOT, "label": "WAGO principal (aucune section)"},
            *[{"value": path, "label": path} for path in paths],
            {"value": SECTION_NEW, "label": "➕ Nouvelle section / sous-section"},
        ]
        return SelectSelector(
            SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
        )

    async def async_step_point_form(self, user_input=None) -> ConfigFlowResult:
        points, defaults = await self._prepare_point_defaults()
        current_section = normalize_section_path(defaults.get("section", ""))
        if user_input is not None:
            self._point_draft = {
                "id": slugify(str(user_input["id"])),
                "name": str(user_input["name"]).strip(),
                "enabled": bool(user_input["enabled"]),
                "platform": str(user_input["platform"]),
            }
            if self._point_action == "edit" and self._point_original:
                self._point_draft["id"] = self._point_original["id"]
            section_choice = str(user_input["section_choice"])
            if section_choice == SECTION_NEW:
                return await self.async_step_new_section()
            self._point_draft["section"] = (
                "" if section_choice == SECTION_ROOT else normalize_section_path(section_choice)
            )
            return await self.async_step_point_modbus()

        return self.async_show_form(
            step_id="point_form",
            data_schema=vol.Schema(
                {
                    vol.Required("id", default=defaults.get("id", "")): TextSelector(
                        TextSelectorConfig()
                    ),
                    vol.Required("name", default=defaults.get("name", "")): TextSelector(
                        TextSelectorConfig()
                    ),
                    vol.Required("enabled", default=defaults.get("enabled", True)): bool,
                    vol.Required(
                        "platform", default=defaults.get("platform", PLATFORM_SENSOR)
                    ): select(PLATFORM_LABELS),
                    vol.Required(
                        "section_choice", default=current_section or SECTION_ROOT
                    ): self._section_selector(points, current_section),
                }
            ),
        )

    async def async_step_new_section(self, user_input=None) -> ConfigFlowResult:
        points = await async_load_points(self.hass, self._entry.entry_id)
        paths = section_paths_from_points(points)
        parent_options = {SECTION_ROOT: "Aucune — section racine"}
        parent_options.update({path: path for path in paths})
        schema = vol.Schema(
            {
                vol.Required("parent_section", default=SECTION_ROOT): select(parent_options),
                vol.Required("section_name"): TextSelector(TextSelectorConfig()),
            }
        )
        if user_input is not None:
            name = normalize_section_path(user_input["section_name"])
            if not name:
                return self.async_show_form(
                    step_id="new_section",
                    data_schema=schema,
                    errors={"base": "section_required"},
                )
            parent = str(user_input["parent_section"])
            self._point_draft["section"] = (
                name
                if parent == SECTION_ROOT
                else normalize_section_path(f"{parent} / {name}")
            )
            return await self.async_step_point_modbus()
        return self.async_show_form(step_id="new_section", data_schema=schema)

    def _allowed_tables(self, platform: str) -> dict[str, str]:
        if platform in (PLATFORM_NUMBER, PLATFORM_SELECT):
            allowed = (TABLE_HOLDING,)
        elif platform in (PLATFORM_SWITCH, PLATFORM_BUTTON):
            allowed = (TABLE_COIL, TABLE_HOLDING)
        else:
            allowed = (TABLE_COIL, TABLE_DISCRETE, TABLE_HOLDING, TABLE_INPUT)
        return {table: TABLE_LABELS[table] for table in allowed}

    async def async_step_point_modbus(self, user_input=None) -> ConfigFlowResult:
        defaults = self._point_original
        platform = self._point_draft["platform"]
        allowed = self._allowed_tables(platform)
        default_table = str(defaults.get("table", next(iter(allowed))))
        if default_table not in allowed:
            default_table = next(iter(allowed))
        if user_input is not None:
            self._point_draft["table"] = str(user_input["table"])
            self._point_draft["address"] = int(user_input["address"])
            if self._point_draft["table"] in (TABLE_COIL, TABLE_DISCRETE):
                self._point_draft["data_type"] = DATA_BOOL
                return await self.async_step_point_details()
            return await self.async_step_point_register()
        return self.async_show_form(
            step_id="point_modbus",
            data_schema=vol.Schema(
                {
                    vol.Required("table", default=default_table): select(allowed),
                    vol.Required(
                        "address", default=int(defaults.get("address", 0))
                    ): box(0, 65535),
                }
            ),
        )

    async def async_step_point_register(self, user_input=None) -> ConfigFlowResult:
        defaults = self._point_original
        platform = self._point_draft["platform"]
        data_types = [item for item in DATA_TYPES if item != DATA_BOOL]
        show_bit = platform in (
            PLATFORM_BINARY_SENSOR,
            PLATFORM_SWITCH,
            PLATFORM_BUTTON,
        )
        if user_input is not None:
            self._point_draft["data_type"] = str(user_input["data_type"])
            bit = user_input.get("bit")
            if show_bit and bit is not None:
                self._point_draft["bit"] = int(bit)
            return await self.async_step_point_details()
        fields: dict[Any, Any] = {
            vol.Required(
                "data_type", default=defaults.get("data_type", DATA_UINT16)
            ): select(data_types)
        }
        if show_bit:
            default_bit = defaults.get("bit")
            marker = (
                vol.Optional("bit", default=int(default_bit))
                if default_bit is not None
                else vol.Optional("bit")
            )
            fields[marker] = box(0, 15)
        return self.async_show_form(
            step_id="point_register", data_schema=vol.Schema(fields)
        )

    def _details_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        platform = self._point_draft["platform"]
        table = self._point_draft["table"]
        data_type = self._point_draft.get("data_type", DATA_BOOL)
        fields: dict[Any, Any] = {}

        if platform in (PLATFORM_SENSOR, PLATFORM_NUMBER):
            fields[vol.Required("scale", default=float(defaults.get("scale", 1.0)))] = box(
                -1000000, 1000000, 0.001
            )
            fields[vol.Required("offset", default=float(defaults.get("offset", 0.0)))] = box(
                -1000000, 1000000, 0.001
            )
            fields[vol.Optional("unit", default=defaults.get("unit", ""))] = TextSelector(
                TextSelectorConfig()
            )

        if platform == PLATFORM_SENSOR:
            precision = defaults.get("precision")
            fields[
                vol.Optional("precision", default=int(precision))
                if precision is not None
                else vol.Optional("precision")
            ] = box(0, 6)
            fields[
                vol.Optional("device_class", default=defaults.get("device_class", ""))
            ] = TextSelector(TextSelectorConfig())
            fields[
                vol.Optional("state_class", default=defaults.get("state_class", ""))
            ] = TextSelector(TextSelectorConfig())

        if platform == PLATFORM_NUMBER:
            for key, fallback in (("min", 0.0), ("max", 100.0), ("step", 1.0)):
                fields[vol.Required(key, default=float(defaults.get(key, fallback)))] = box(
                    -1000000000 if key != "step" else 0.001,
                    1000000000,
                    0.001,
                )
            fields[
                vol.Required(
                    "read_after_write", default=defaults.get("read_after_write", True)
                )
            ] = bool

        if platform in (PLATFORM_BINARY_SENSOR, PLATFORM_SWITCH):
            fields[vol.Required("inverted", default=defaults.get("inverted", False))] = bool
            if platform == PLATFORM_SWITCH:
                fields[
                    vol.Required(
                        "read_after_write", default=defaults.get("read_after_write", True)
                    )
                ] = bool

        if platform == PLATFORM_BUTTON:
            fields[
                vol.Required(
                    "command_mode", default=defaults.get("command_mode", "pulse")
                )
            ] = select({"normal": "Écriture simple", "pulse": "Impulsion"})
            fields[
                vol.Required(
                    "active_value", default=float(defaults.get("active_value", 1))
                )
            ] = box(-1000000000, 1000000000, 0.001)
            fields[
                vol.Required("pulse_ms", default=int(defaults.get("pulse_ms", 300)))
            ] = box(0, 60000)
            fields[
                vol.Required(
                    "return_value", default=float(defaults.get("return_value", 0))
                )
            ] = box(-1000000000, 1000000000, 0.001)

        if platform == PLATFORM_SELECT:
            fields[
                vol.Required(
                    "select_options", default=defaults.get("select_options", "")
                )
            ] = TextSelector(TextSelectorConfig(multiline=False))
            fields[
                vol.Required(
                    "read_after_write", default=defaults.get("read_after_write", True)
                )
            ] = bool

        if table in (TABLE_HOLDING, TABLE_INPUT) and register_count(data_type) > 1:
            fields[
                vol.Required("byte_order", default=defaults.get("byte_order", "big"))
            ] = select({"big": "Big endian", "little": "Little endian"})
            fields[
                vol.Required("word_order", default=defaults.get("word_order", "big"))
            ] = select({"big": "Big endian", "little": "Little endian"})

        fields[vol.Optional("icon", default=defaults.get("icon", ""))] = TextSelector(
            TextSelectorConfig()
        )
        return vol.Schema(fields)

    async def async_step_point_details(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            self._point_draft.update(user_input)
            return await self._save_point_draft()
        return self.async_show_form(
            step_id="point_details", data_schema=self._details_schema(self._point_original)
        )

    async def _save_point_draft(self) -> ConfigFlowResult:
        points = await async_load_points(self.hass, self._entry.entry_id)
        original = self._point_original
        platform = self._point_draft["platform"]
        point: dict[str, Any] = {
            "enabled": bool(self._point_draft.get("enabled", True)),
            "id": slugify(str(self._point_draft["id"])),
            "section": normalize_section_path(self._point_draft.get("section", "")),
            "name": str(self._point_draft["name"]).strip(),
            "platform": platform,
            "table": self._point_draft["table"],
            "address": int(self._point_draft["address"]),
            "data_type": self._point_draft.get("data_type", DATA_BOOL),
            "scale": float(self._point_draft.get("scale", 1.0)),
            "offset": float(self._point_draft.get("offset", 0.0)),
            "unit": str(self._point_draft.get("unit", "")),
            "device_class": str(self._point_draft.get("device_class", "")),
            "state_class": str(self._point_draft.get("state_class", "")),
            "read": platform != PLATFORM_BUTTON,
            "write": platform in WRITABLE_PLATFORMS,
            "inverted": bool(self._point_draft.get("inverted", False)),
            "read_after_write": bool(self._point_draft.get("read_after_write", True)),
            "byte_order": str(self._point_draft.get("byte_order", "big")),
            "word_order": str(self._point_draft.get("word_order", "big")),
            "command_mode": str(
                self._point_draft.get(
                    "command_mode", "pulse" if platform == PLATFORM_BUTTON else "normal"
                )
            ),
            "pulse_ms": int(self._point_draft.get("pulse_ms", 300)),
            "active_value": self._point_draft.get("active_value", 1),
            "return_value": self._point_draft.get("return_value", 0),
            "select_options": str(self._point_draft.get("select_options", "")),
            "icon": str(self._point_draft.get("icon", "")),
            "notes": str(original.get("notes", "")),
        }
        for key in ("bit", "precision", "min", "max", "step"):
            if key in self._point_draft and self._point_draft[key] is not None:
                point[key] = self._point_draft[key]
        if self._point_action == "edit" and original:
            point["id"] = original["id"]

        if self._point_action in ("add", "duplicate") and len(points) >= MAX_POINTS:
            return self.async_show_form(
                step_id="point_details",
                data_schema=self._details_schema(original),
                errors={"base": "too_many_points"},
                description_placeholders={"details": ""},
            )

        candidate = [p for p in points if p.get("id") != original.get("id")]
        candidate.append(point)
        point_errors, _ = validate_points(candidate, memory_for_entry(self._entry))
        if point_errors:
            return self.async_show_form(
                step_id="point_details",
                data_schema=self._details_schema(original),
                errors={"base": "invalid_point"},
                description_placeholders={"details": "\n".join(point_errors[:5])},
            )
        await async_save_points(self.hass, self._entry.entry_id, candidate)
        return self._finish_points_change()

    async def async_step_delete_point(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            if not user_input.get("confirm"):
                return self.async_show_form(
                    step_id="delete_point",
                    data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
                    errors={"base": "confirmation_required"},
                )
            points = await async_load_points(self.hass, self._entry.entry_id)
            points = [p for p in points if p.get("id") != self._selected_point_id]
            await async_save_points(self.hass, self._entry.entry_id, points)
            return self._finish_points_change()
        return self.async_show_form(
            step_id="delete_point",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
        )
