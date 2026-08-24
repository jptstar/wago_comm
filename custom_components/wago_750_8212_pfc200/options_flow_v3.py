"""Polished point editor for WAGO 750-8212 PFC200."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.components.number.const import NumberDeviceClass
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
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
from .flow_helpers import box, memory_for_entry, select
from .options_flow_v2 import WagoOptionsFlowV2
from .point import register_count
from .storage import async_load_points

COMMON_UNITS = (
    "%",
    "°C",
    "°F",
    "bar",
    "mbar",
    "Pa",
    "kPa",
    "hPa",
    "psi",
    "L",
    "m³",
    "L/min",
    "L/h",
    "m³/h",
    "s",
    "min",
    "h",
    "V",
    "mV",
    "A",
    "mA",
    "W",
    "kW",
    "Wh",
    "kWh",
    "Hz",
    "rpm",
    "m",
    "cm",
    "mm",
    "mm/h",
    "lux",
    "ppm",
    "g/L",
    "mg/L",
    "µS/cm",
    "mS/cm",
    "pH",
)

MAX_ADDRESS_SUGGESTIONS = 512


def _humanize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").capitalize()


def _custom_dropdown(
    values: list[str] | tuple[str, ...],
    current: str = "",
    *,
    none_label: str = "Aucune",
) -> SelectSelector:
    """Return a dropdown with suggested values and manual input enabled."""
    options: list[dict[str, str]] = [{"value": "", "label": none_label}]
    seen = {""}
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        options.append({"value": text, "label": f"{_humanize(text)} ({text})"})
    if current and current not in seen:
        options.append({"value": current, "label": f"{current} — valeur actuelle"})
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _unit_dropdown(current: str = "") -> SelectSelector:
    options: list[dict[str, str]] = [{"value": "", "label": "Aucune unité"}]
    seen = {""}
    for value in COMMON_UNITS:
        if value not in seen:
            seen.add(value)
            options.append({"value": value, "label": value})
    if current and current not in seen:
        options.append({"value": current, "label": f"{current} — unité actuelle"})
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            custom_value=True,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


class WagoOptionsFlowV3(WagoOptionsFlowV2):
    """Improve address selection, metadata selectors and point-editor text."""

    async def async_step_point_modbus(self, user_input=None) -> ConfigFlowResult:
        """Choose the Modbus table before choosing an address."""
        defaults = self._point_original
        platform = self._point_draft["platform"]
        allowed = self._allowed_tables(platform)
        default_table = str(
            self._point_draft.get(
                "table",
                defaults.get("table", next(iter(allowed))),
            )
        )
        if default_table not in allowed:
            default_table = next(iter(allowed))

        if user_input is not None:
            if user_input.get("back"):
                return await self.async_step_point_form()
            self._point_draft["table"] = str(user_input["table"])
            self._point_draft.pop("address", None)
            return await self.async_step_point_address()

        result = self.async_show_form(
            step_id="point_modbus",
            data_schema=vol.Schema(
                {
                    vol.Required("table", default=default_table): select(allowed),
                }
            ),
        )
        return self._form_with_back(result)

    async def _address_selector(self, table: str) -> SelectSelector:
        """Build address choices from the configured memory block."""
        points = await async_load_points(self.hass, self._entry.entry_id)
        start, size = memory_for_entry(self._entry)[table]
        used: dict[int, list[str]] = {}
        current_id = self._point_original.get("id")
        for point in points:
            if point.get("table") != table or point.get("id") == current_id:
                continue
            try:
                address = int(point.get("address"))
            except (TypeError, ValueError):
                continue
            used.setdefault(address, []).append(str(point.get("name") or point.get("id")))

        addresses: list[int] = []
        if size > 0:
            addresses.extend(range(start, start + min(size, MAX_ADDRESS_SUGGESTIONS)))

        current_address = self._point_draft.get(
            "address", self._point_original.get("address")
        )
        current_int: int | None = None
        if current_address is not None:
            try:
                current_int = int(current_address)
            except (TypeError, ValueError):
                current_int = None
            if current_int is not None and current_int not in addresses:
                addresses.append(current_int)

        options: list[dict[str, str]] = []
        for address in sorted(set(addresses)):
            names = used.get(address, [])
            if names:
                preview = ", ".join(names[:2])
                if len(names) > 2:
                    preview += f" +{len(names) - 2}"
                label = f"{address} — déjà utilisé : {preview}"
            elif current_int is not None and address == current_int:
                label = f"{address} — adresse actuelle"
            else:
                label = f"{address} — disponible"
            options.append({"value": str(address), "label": label})

        return SelectSelector(
            SelectSelectorConfig(
                options=options,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )

    async def async_step_point_address(self, user_input=None) -> ConfigFlowResult:
        """Choose one address, with configured/used addresses suggested."""
        table = str(self._point_draft["table"])
        start, size = memory_for_entry(self._entry)[table]
        end = start + max(0, size) - 1
        default_address = self._point_draft.get(
            "address",
            self._point_original.get("address", start),
        )

        if user_input is not None:
            if user_input.get("back"):
                return await self.async_step_point_modbus()
            try:
                address = int(str(user_input["address"]).strip())
            except (TypeError, ValueError):
                return self.async_show_form(
                    step_id="point_address",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                "address", default=str(default_address)
                            ): await self._address_selector(table),
                            vol.Optional("back", default=False): bool,
                        }
                    ),
                    errors={"base": "invalid_address"},
                )
            if size <= 0 or address < start or address > end:
                return self.async_show_form(
                    step_id="point_address",
                    data_schema=vol.Schema(
                        {
                            vol.Required(
                                "address", default=str(address)
                            ): await self._address_selector(table),
                            vol.Optional("back", default=False): bool,
                        }
                    ),
                    errors={"base": "address_out_of_range"},
                )

            self._point_draft["address"] = address
            if table in (TABLE_COIL, TABLE_DISCRETE):
                self._point_draft["data_type"] = DATA_BOOL
                return await self.async_step_point_details()
            return await self.async_step_point_register()

        result = self.async_show_form(
            step_id="point_address",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "address", default=str(default_address)
                    ): await self._address_selector(table),
                }
            ),
        )
        return self._form_with_back(result)

    async def async_step_point_register(self, user_input=None) -> ConfigFlowResult:
        """Choose register data type, preserving choices when going back."""
        defaults = self._point_original
        platform = self._point_draft["platform"]
        data_types = [item for item in DATA_TYPES if item != DATA_BOOL]
        show_bit = platform in (
            PLATFORM_BINARY_SENSOR,
            PLATFORM_SWITCH,
            PLATFORM_BUTTON,
        )
        default_data_type = self._point_draft.get(
            "data_type", defaults.get("data_type", DATA_UINT16)
        )

        if user_input is not None:
            if user_input.get("back"):
                return await self.async_step_point_address()
            self._point_draft["data_type"] = str(user_input["data_type"])
            bit = user_input.get("bit")
            if show_bit and bit is not None:
                self._point_draft["bit"] = int(bit)
            else:
                self._point_draft.pop("bit", None)
            return await self.async_step_point_details()

        fields: dict[Any, Any] = {
            vol.Required("data_type", default=default_data_type): select(data_types)
        }
        if show_bit:
            default_bit = self._point_draft.get("bit", defaults.get("bit"))
            marker = (
                vol.Optional("bit", default=int(default_bit))
                if default_bit is not None
                else vol.Optional("bit")
            )
            fields[marker] = box(0, 15)

        result = self.async_show_form(
            step_id="point_register", data_schema=vol.Schema(fields)
        )
        return self._form_with_back(result)

    def _details_schema(self, defaults: dict[str, Any]) -> vol.Schema:
        """Only expose parameters that make sense for the selected entity."""
        platform = self._point_draft["platform"]
        table = self._point_draft["table"]
        data_type = self._point_draft.get("data_type", DATA_BOOL)
        fields: dict[Any, Any] = {}

        if platform in (PLATFORM_SENSOR, PLATFORM_NUMBER):
            fields[
                vol.Required(
                    "scale",
                    default=float(
                        self._point_draft.get("scale", defaults.get("scale", 1.0))
                    ),
                )
            ] = box(-1000000, 1000000, 0.001)
            fields[
                vol.Required(
                    "offset",
                    default=float(
                        self._point_draft.get("offset", defaults.get("offset", 0.0))
                    ),
                )
            ] = box(-1000000, 1000000, 0.001)
            current_unit = str(
                self._point_draft.get("unit", defaults.get("unit", ""))
            )
            fields[vol.Optional("unit", default=current_unit)] = _unit_dropdown(
                current_unit
            )

        if platform == PLATFORM_SENSOR:
            precision = self._point_draft.get(
                "precision", defaults.get("precision")
            )
            fields[
                vol.Optional("precision", default=int(precision))
                if precision is not None
                else vol.Optional("precision")
            ] = box(0, 6)

            current_device_class = str(
                self._point_draft.get(
                    "device_class", defaults.get("device_class", "")
                )
            )
            fields[
                vol.Optional("device_class", default=current_device_class)
            ] = _custom_dropdown(
                [item.value for item in SensorDeviceClass],
                current_device_class,
            )

            current_state_class = str(
                self._point_draft.get(
                    "state_class", defaults.get("state_class", "")
                )
            )
            fields[
                vol.Optional("state_class", default=current_state_class)
            ] = _custom_dropdown(
                [item.value for item in SensorStateClass],
                current_state_class,
            )

        if platform == PLATFORM_NUMBER:
            for key, fallback in (("min", 0.0), ("max", 100.0), ("step", 1.0)):
                value = float(
                    self._point_draft.get(key, defaults.get(key, fallback))
                )
                fields[vol.Required(key, default=value)] = box(
                    -1000000000 if key != "step" else 0.001,
                    1000000000,
                    0.001,
                )
            current_device_class = str(
                self._point_draft.get(
                    "device_class", defaults.get("device_class", "")
                )
            )
            fields[
                vol.Optional("device_class", default=current_device_class)
            ] = _custom_dropdown(
                [item.value for item in NumberDeviceClass],
                current_device_class,
            )
            fields[
                vol.Required(
                    "read_after_write",
                    default=bool(
                        self._point_draft.get(
                            "read_after_write",
                            defaults.get("read_after_write", True),
                        )
                    ),
                )
            ] = bool

        if platform == PLATFORM_BINARY_SENSOR:
            current_device_class = str(
                self._point_draft.get(
                    "device_class", defaults.get("device_class", "")
                )
            )
            fields[
                vol.Optional("device_class", default=current_device_class)
            ] = _custom_dropdown(
                [item.value for item in BinarySensorDeviceClass],
                current_device_class,
            )
            fields[
                vol.Required(
                    "inverted",
                    default=bool(
                        self._point_draft.get(
                            "inverted", defaults.get("inverted", False)
                        )
                    ),
                )
            ] = bool

        if platform == PLATFORM_SWITCH:
            fields[
                vol.Required(
                    "inverted",
                    default=bool(
                        self._point_draft.get(
                            "inverted", defaults.get("inverted", False)
                        )
                    ),
                )
            ] = bool
            fields[
                vol.Required(
                    "read_after_write",
                    default=bool(
                        self._point_draft.get(
                            "read_after_write",
                            defaults.get("read_after_write", True),
                        )
                    ),
                )
            ] = bool

        if platform == PLATFORM_BUTTON:
            fields[
                vol.Required(
                    "command_mode",
                    default=str(
                        self._point_draft.get(
                            "command_mode",
                            defaults.get("command_mode", "pulse"),
                        )
                    ),
                )
            ] = select({"normal": "Écriture simple", "pulse": "Impulsion"})
            fields[
                vol.Required(
                    "active_value",
                    default=float(
                        self._point_draft.get(
                            "active_value", defaults.get("active_value", 1)
                        )
                    ),
                )
            ] = box(-1000000000, 1000000000, 0.001)
            fields[
                vol.Required(
                    "pulse_ms",
                    default=int(
                        self._point_draft.get(
                            "pulse_ms", defaults.get("pulse_ms", 300)
                        )
                    ),
                )
            ] = box(0, 60000)
            fields[
                vol.Required(
                    "return_value",
                    default=float(
                        self._point_draft.get(
                            "return_value", defaults.get("return_value", 0)
                        )
                    ),
                )
            ] = box(-1000000000, 1000000000, 0.001)

        if platform == PLATFORM_SELECT:
            current_options = str(
                self._point_draft.get(
                    "select_options", defaults.get("select_options", "")
                )
            )
            fields[
                vol.Required("select_options", default=current_options)
            ] = TextSelector(TextSelectorConfig(multiline=False))
            fields[
                vol.Required(
                    "read_after_write",
                    default=bool(
                        self._point_draft.get(
                            "read_after_write",
                            defaults.get("read_after_write", True),
                        )
                    ),
                )
            ] = bool

        if table in (TABLE_HOLDING, TABLE_INPUT) and register_count(data_type) > 1:
            fields[
                vol.Required(
                    "byte_order",
                    default=str(
                        self._point_draft.get(
                            "byte_order", defaults.get("byte_order", "big")
                        )
                    ),
                )
            ] = select({"big": "Big endian", "little": "Little endian"})
            fields[
                vol.Required(
                    "word_order",
                    default=str(
                        self._point_draft.get(
                            "word_order", defaults.get("word_order", "big")
                        )
                    ),
                )
            ] = select({"big": "Big endian", "little": "Little endian"})

        current_icon = str(
            self._point_draft.get("icon", defaults.get("icon", ""))
        )
        fields[vol.Optional("icon", default=current_icon)] = TextSelector(
            TextSelectorConfig()
        )
        return vol.Schema(fields)

    async def async_step_point_details(self, user_input=None) -> ConfigFlowResult:
        """Return to the immediately previous wizard step."""
        if user_input is not None and user_input.get("back"):
            values = dict(user_input)
            values.pop("back", None)
            self._point_draft.update(values)
            if self._point_draft.get("table") in (TABLE_HOLDING, TABLE_INPUT):
                return await self.async_step_point_register()
            return await self.async_step_point_address()
        return await super().async_step_point_details(user_input)
