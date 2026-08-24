"""Config and options flows for WAGO 750-8212 PFC200."""

from __future__ import annotations

import csv
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .api import WagoCommunicationError, WagoModbusClient
from .const import (
    CONF_COIL_SIZE,
    CONF_COIL_START,
    CONF_DISCRETE_SIZE,
    CONF_DISCRETE_START,
    CONF_HOLDING_SIZE,
    CONF_HOLDING_START,
    CONF_INPUT_SIZE,
    CONF_INPUT_START,
    CONF_POINTS_REVISION,
    CONF_RECONNECT_DELAY,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DATA_TYPES,
    DEFAULT_MEMORY,
    DEFAULT_PORT,
    DEFAULT_RECONNECT_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MAX_POINTS,
    TABLE_COIL,
    TABLE_DISCRETE,
    TABLE_HOLDING,
    TABLE_INPUT,
)
from .csv_io import export_csv_text, parse_csv_text, validate_points
from .point import slugify
from .storage import async_load_points, async_save_points


def _box(minimum: float, maximum: float, step: float = 1) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=NumberSelectorMode.BOX,
        )
    )


def _select(options: list[str] | dict[str, str]) -> SelectSelector:
    rendered = (
        [{"value": value, "label": label} for value, label in options.items()]
        if isinstance(options, dict)
        else options
    )
    return SelectSelector(
        SelectSelectorConfig(options=rendered, mode=SelectSelectorMode.DROPDOWN)
    )


def _effective(entry: ConfigEntry, key: str, default: Any) -> Any:
    return entry.options.get(key, entry.data.get(key, default))


def _memory_from_values(values: dict[str, Any]) -> dict[str, tuple[int, int]]:
    return {
        TABLE_COIL: (int(values[CONF_COIL_START]), int(values[CONF_COIL_SIZE])),
        TABLE_DISCRETE: (
            int(values[CONF_DISCRETE_START]),
            int(values[CONF_DISCRETE_SIZE]),
        ),
        TABLE_HOLDING: (
            int(values[CONF_HOLDING_START]),
            int(values[CONF_HOLDING_SIZE]),
        ),
        TABLE_INPUT: (int(values[CONF_INPUT_START]), int(values[CONF_INPUT_SIZE])),
    }


def _memory_for_entry(entry: ConfigEntry) -> dict[str, tuple[int, int]]:
    values = {
        key: _effective(entry, key, default) for key, default in DEFAULT_MEMORY.items()
    }
    return _memory_from_values(values)


def _connection_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(
                CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)
            ): _box(0, 247),
            vol.Required(
                CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): _box(0.5, 60, 0.5),
            vol.Required(
                CONF_RECONNECT_DELAY,
                default=defaults.get(CONF_RECONNECT_DELAY, DEFAULT_RECONNECT_DELAY),
            ): _box(0, 300),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): _box(1, 300),
        }
    )


def _memory_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or DEFAULT_MEMORY
    fields: dict[Any, Any] = {}
    for start_key, size_key in (
        (CONF_COIL_START, CONF_COIL_SIZE),
        (CONF_DISCRETE_START, CONF_DISCRETE_SIZE),
        (CONF_HOLDING_START, CONF_HOLDING_SIZE),
        (CONF_INPUT_START, CONF_INPUT_SIZE),
    ):
        fields[
            vol.Required(
                start_key, default=int(defaults.get(start_key, DEFAULT_MEMORY[start_key]))
            )
        ] = _box(0, 65535)
        fields[
            vol.Required(
                size_key, default=int(defaults.get(size_key, DEFAULT_MEMORY[size_key]))
            )
        ] = _box(0, 65535)
    return vol.Schema(fields)


async def _test_connection(data: dict[str, Any]) -> None:
    api = WagoModbusClient(
        host=data[CONF_HOST],
        port=int(data[CONF_PORT]),
        timeout=float(data[CONF_TIMEOUT]),
        reconnect_delay=float(data[CONF_RECONNECT_DELAY]),
        unit_id=int(data[CONF_UNIT_ID]),
    )
    try:
        await api.async_connect()
    finally:
        await api.async_close()


class WagoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a WAGO controller."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _test_connection(user_input)
            except (WagoCommunicationError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                self._connection = dict(user_input)
                return await self.async_step_memory()
        return self.async_show_form(
            step_id="user",
            data_schema=_connection_schema(user_input),
            errors=errors,
        )

    async def async_step_memory(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            data = {**self._connection, **user_input}
            unique_id = (
                f"{data[CONF_HOST]}:{data[CONF_PORT]}:{int(data[CONF_UNIT_ID])}"
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"WAGO PFC200 {data[CONF_HOST]}", data=data
            )
        return self.async_show_form(step_id="memory", data_schema=_memory_schema())

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        defaults = {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data[CONF_PORT],
            CONF_UNIT_ID: _effective(entry, CONF_UNIT_ID, DEFAULT_UNIT_ID),
            CONF_TIMEOUT: _effective(entry, CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_RECONNECT_DELAY: _effective(
                entry, CONF_RECONNECT_DELAY, DEFAULT_RECONNECT_DELAY
            ),
            CONF_SCAN_INTERVAL: _effective(
                entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            ),
        }
        if user_input is not None:
            try:
                await _test_connection(user_input)
            except (WagoCommunicationError, OSError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                new_data = dict(entry.data)
                new_data.update(user_input)
                unique_id = (
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}:"
                    f"{int(user_input[CONF_UNIT_ID])}"
                )
                existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, unique_id
                )
                if existing is not None and existing.entry_id != entry.entry_id:
                    return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                    unique_id=unique_id,
                    title=f"WAGO PFC200 {user_input[CONF_HOST]}",
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return WagoOptionsFlow(config_entry)


class WagoOptionsFlow(config_entries.OptionsFlow):
    """Manage communication, memory and point definitions."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._selected_point_id: str | None = None
        self._point_action: str | None = None
        self._import_points: list[dict[str, Any]] = []
        self._import_warnings: list[str] = []
        self._import_mode = "replace"

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "communication",
                "memory",
                "points",
                "import_csv",
                "export_csv",
            ],
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
                        CONF_UNIT_ID,
                        default=_effective(self._entry, CONF_UNIT_ID, DEFAULT_UNIT_ID),
                    ): _box(0, 247),
                    vol.Required(
                        CONF_TIMEOUT,
                        default=_effective(self._entry, CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): _box(0.5, 60, 0.5),
                    vol.Required(
                        CONF_RECONNECT_DELAY,
                        default=_effective(
                            self._entry,
                            CONF_RECONNECT_DELAY,
                            DEFAULT_RECONNECT_DELAY,
                        ),
                    ): _box(0, 300),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=_effective(
                            self._entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): _box(1, 300),
                }
            ),
        )

    async def async_step_memory(self, user_input=None) -> ConfigFlowResult:
        defaults = {
            key: _effective(self._entry, key, default)
            for key, default in DEFAULT_MEMORY.items()
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            points = await async_load_points(self.hass, self._entry.entry_id)
            point_errors, _ = validate_points(points, _memory_from_values(user_input))
            if point_errors:
                errors["base"] = "memory_conflict"
            else:
                data = dict(self._entry.options)
                data.update(user_input)
                return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="memory",
            data_schema=_memory_schema(defaults),
            errors=errors,
        )

    async def async_step_points(self, user_input=None) -> ConfigFlowResult:
        points = await async_load_points(self.hass, self._entry.entry_id)
        if user_input is not None:
            action = user_input["action"]
            self._point_action = action
            self._selected_point_id = user_input.get("point_id") or None
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
                ),
            }
            for p in points
        ]
        fields: dict[Any, Any] = {
            vol.Required("action", default="add"): _select(
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
                    options=point_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        return vol.Schema(fields)

    def _point_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        def opt_num(
            key: str, minimum: float, maximum: float, step: float = 1
        ) -> tuple[Any, NumberSelector]:
            default = defaults.get(key)
            marker = (
                vol.Optional(key, default=default)
                if default is not None
                else vol.Optional(key)
            )
            return marker, _box(minimum, maximum, step)

        fields: dict[Any, Any] = {
            vol.Required("id", default=defaults.get("id", "")): TextSelector(
                TextSelectorConfig()
            ),
            vol.Required("name", default=defaults.get("name", "")): TextSelector(
                TextSelectorConfig()
            ),
            vol.Optional(
                "section", default=defaults.get("section", "")
            ): TextSelector(TextSelectorConfig()),
            vol.Required("enabled", default=defaults.get("enabled", True)): bool,
            vol.Required(
                "platform", default=defaults.get("platform", "sensor")
            ): _select(
                {
                    "sensor": "Capteur",
                    "binary_sensor": "Capteur binaire",
                    "switch": "Interrupteur",
                    "number": "Nombre",
                    "button": "Bouton",
                    "select": "Liste de sélection",
                }
            ),
            vol.Required(
                "table", default=defaults.get("table", TABLE_HOLDING)
            ): _select(
                {
                    "coil": "Coil",
                    "discrete_input": "Discrete Input",
                    "holding_register": "Holding Register",
                    "input_register": "Input Register",
                }
            ),
            vol.Required(
                "address", default=int(defaults.get("address", 0))
            ): _box(0, 65535),
            vol.Required(
                "data_type", default=defaults.get("data_type", "uint16")
            ): _select(list(DATA_TYPES)),
            vol.Required(
                "scale", default=float(defaults.get("scale", 1.0))
            ): _box(-1000000, 1000000, 0.001),
            vol.Required(
                "offset", default=float(defaults.get("offset", 0.0))
            ): _box(-1000000, 1000000, 0.001),
            vol.Optional("unit", default=defaults.get("unit", "")): TextSelector(
                TextSelectorConfig()
            ),
            vol.Optional(
                "device_class", default=defaults.get("device_class", "")
            ): TextSelector(TextSelectorConfig()),
            vol.Optional(
                "state_class", default=defaults.get("state_class", "")
            ): TextSelector(TextSelectorConfig()),
            vol.Required("read", default=defaults.get("read", True)): bool,
            vol.Required("write", default=defaults.get("write", False)): bool,
            vol.Required(
                "inverted", default=defaults.get("inverted", False)
            ): bool,
            vol.Required(
                "read_after_write", default=defaults.get("read_after_write", True)
            ): bool,
            vol.Required(
                "byte_order", default=defaults.get("byte_order", "big")
            ): _select({"big": "Big endian", "little": "Little endian"}),
            vol.Required(
                "word_order", default=defaults.get("word_order", "big")
            ): _select({"big": "Big endian", "little": "Little endian"}),
            vol.Required(
                "command_mode", default=defaults.get("command_mode", "pulse")
            ): _select(
                {"normal": "Écriture normale", "pulse": "Impulsion"}
            ),
            vol.Optional(
                "select_options", default=defaults.get("select_options", "")
            ): TextSelector(TextSelectorConfig(multiline=False)),
            vol.Optional("icon", default=defaults.get("icon", "")): TextSelector(
                TextSelectorConfig()
            ),
        }
        for marker, selector in (
            opt_num("bit", 0, 15),
            opt_num("precision", 0, 6),
            opt_num("min", -1000000000, 1000000000, 0.001),
            opt_num("max", -1000000000, 1000000000, 0.001),
            opt_num("step", 0.001, 1000000000, 0.001),
            opt_num("pulse_ms", 0, 60000),
            opt_num("active_value", -1000000000, 1000000000, 0.001),
            opt_num("return_value", -1000000000, 1000000000, 0.001),
        ):
            fields[marker] = selector
        return vol.Schema(fields)

    async def async_step_point_form(self, user_input=None) -> ConfigFlowResult:
        points = await async_load_points(self.hass, self._entry.entry_id)
        original = next(
            (p for p in points if p.get("id") == self._selected_point_id), {}
        )
        defaults = dict(original)
        if self._point_action == "duplicate" and defaults:
            defaults["id"] = f"{defaults['id']}_copy"
            defaults["name"] = f"{defaults.get('name', defaults['id'])} copie"
        errors: dict[str, str] = {}
        if user_input is not None:
            point = dict(user_input)
            point["id"] = slugify(str(point["id"]))
            if self._point_action == "edit" and original:
                point["id"] = original["id"]
            if self._point_action in ("add", "duplicate") and len(points) >= MAX_POINTS:
                errors["base"] = "too_many_points"
            else:
                candidate = [
                    p for p in points if p.get("id") != original.get("id")
                ]
                candidate.append(point)
                point_errors, _ = validate_points(
                    candidate, _memory_for_entry(self._entry)
                )
                if point_errors:
                    errors["base"] = "invalid_point"
                else:
                    await async_save_points(
                        self.hass, self._entry.entry_id, candidate
                    )
                    return self._finish_points_change()
        return self.async_show_form(
            step_id="point_form",
            data_schema=self._point_schema(user_input or defaults),
            errors=errors,
        )

    async def async_step_delete_point(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            if not user_input.get("confirm"):
                return self.async_show_form(
                    step_id="delete_point",
                    data_schema=vol.Schema(
                        {vol.Required("confirm", default=False): bool}
                    ),
                    errors={"base": "confirmation_required"},
                )
            points = await async_load_points(self.hass, self._entry.entry_id)
            points = [
                p for p in points if p.get("id") != self._selected_point_id
            ]
            await async_save_points(self.hass, self._entry.entry_id, points)
            return self._finish_points_change()
        return self.async_show_form(
            step_id="delete_point",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
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
                    text, _memory_for_entry(self._entry)
                )
            except (OSError, UnicodeError, csv.Error, ValueError):
                errors["base"] = "invalid_csv"
            else:
                if parse_errors:
                    errors["base"] = "invalid_csv"
                    placeholders["details"] = "\n".join(parse_errors[:10])
                else:
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
                    vol.Required("mode", default="replace"): _select(
                        {
                            "replace": "Remplacer la table",
                            "merge": "Fusionner par ID",
                        }
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
                    data_schema=vol.Schema(
                        {vol.Required("confirm", default=False): bool}
                    ),
                    errors={"base": "confirmation_required"},
                )
            points = await async_load_points(self.hass, self._entry.entry_id)
            text = export_csv_text(points)
            export_dir = self.hass.config.path("www", "wago_exports")
            export_path = self.hass.config.path(
                "www",
                "wago_exports",
                f"{self._entry.entry_id}_points.csv",
            )

            def _write_export() -> None:
                import os

                os.makedirs(export_dir, exist_ok=True)
                with open(
                    export_path,
                    "w",
                    encoding="utf-8-sig",
                    newline="",
                ) as file_handle:
                    file_handle.write(text)

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
        errors, warnings = validate_points(final, _memory_for_entry(self._entry))
        if errors:
            return self.async_abort(reason="invalid_csv")
        if user_input is not None:
            if not user_input.get("confirm"):
                return self.async_show_form(
                    step_id="import_confirm",
                    data_schema=vol.Schema(
                        {vol.Required("confirm", default=False): bool}
                    ),
                    errors={"base": "confirmation_required"},
                )
            await async_save_points(self.hass, self._entry.entry_id, final)
            return self._finish_points_change()
        counts: dict[str, int] = {}
        for point in final:
            counts[point["table"]] = counts.get(point["table"], 0) + 1
        summary = (
            f"{len(final)} points après import — "
            f"coils {counts.get(TABLE_COIL, 0)}, "
            f"DI {counts.get(TABLE_DISCRETE, 0)}, "
            f"HR {counts.get(TABLE_HOLDING, 0)}, "
            f"IR {counts.get(TABLE_INPUT, 0)}"
        )
        details = (
            "\n".join((self._import_warnings + warnings)[:10])
            or "Aucun avertissement"
        )
        return self.async_show_form(
            step_id="import_confirm",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"summary": summary, "details": details},
        )
