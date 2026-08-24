"""Enhanced options-flow navigation for WAGO 750-8212 PFC200."""

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

from .const import TABLE_HOLDING, TABLE_INPUT
from .flow_helpers import select
from .options_flow import WagoOptionsFlow as BaseWagoOptionsFlow
from .point_options import SECTION_NEW, SECTION_ROOT
from .sections import normalize_section_path, section_paths_from_points
from .storage import async_load_points, async_save_points


class WagoOptionsFlowV2(BaseWagoOptionsFlow):
    """Add explicit back navigation and bulk section moves."""

    def _form_with_back(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Add an explicit Back checkbox to a point-wizard form."""
        schema = result.get("data_schema")
        if isinstance(schema, vol.Schema):
            fields = dict(schema.schema)
            fields[vol.Optional("back", default=False)] = bool
            result["data_schema"] = vol.Schema(fields)
        return result

    async def async_step_points(self, user_input=None) -> ConfigFlowResult:
        """Handle standard point actions plus bulk move and return."""
        if user_input is not None and user_input.get("action") == "back":
            return await self.async_step_init()
        if user_input is not None and user_input.get("action") == "bulk_move":
            self._bulk_point_ids: list[str] = []
            return await self.async_step_bulk_move_select()
        return await super().async_step_points(user_input)

    def _points_schema(self, points: list[dict[str, Any]]) -> vol.Schema:
        """Expose bulk move and Return in the point action list."""
        point_options = [
            {
                "value": point["id"],
                "label": (
                    f"{point.get('section', '')} — {point.get('name', point['id'])} "
                    f"[{point.get('table')} {point.get('address')}]"
                ).lstrip(" —"),
            }
            for point in points
        ]
        fields: dict[Any, Any] = {
            vol.Required("action", default="add"): select(
                {
                    "add": "Ajouter",
                    "edit": "Modifier",
                    "duplicate": "Dupliquer",
                    "delete": "Supprimer",
                    "bulk_move": "Déplacer plusieurs points",
                    "back": "⬅ Retour au menu",
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

    async def async_step_point_form(self, user_input=None) -> ConfigFlowResult:
        """Allow return from the identity step."""
        if user_input is not None and user_input.get("back"):
            return await self.async_step_points()
        return self._form_with_back(await super().async_step_point_form(user_input))

    async def async_step_new_section(self, user_input=None) -> ConfigFlowResult:
        """Allow return from new-section creation."""
        if user_input is not None and user_input.get("back"):
            return await self.async_step_point_form()
        return self._form_with_back(await super().async_step_new_section(user_input))

    async def async_step_point_modbus(self, user_input=None) -> ConfigFlowResult:
        """Allow return from Modbus address selection."""
        if user_input is not None and user_input.get("back"):
            if user_input.get("table") is not None:
                self._point_draft["table"] = str(user_input["table"])
            if user_input.get("address") is not None:
                self._point_draft["address"] = int(user_input["address"])
            return await self.async_step_point_form()
        return self._form_with_back(await super().async_step_point_modbus(user_input))

    async def async_step_point_register(self, user_input=None) -> ConfigFlowResult:
        """Allow return from register-format selection."""
        if user_input is not None and user_input.get("back"):
            if user_input.get("data_type") is not None:
                self._point_draft["data_type"] = str(user_input["data_type"])
            if user_input.get("bit") is not None:
                self._point_draft["bit"] = int(user_input["bit"])
            return await self.async_step_point_modbus()
        return self._form_with_back(await super().async_step_point_register(user_input))

    async def async_step_point_details(self, user_input=None) -> ConfigFlowResult:
        """Allow return from type-specific parameters."""
        if user_input is not None and user_input.get("back"):
            values = dict(user_input)
            values.pop("back", None)
            self._point_draft.update(values)
            if self._point_draft.get("table") in (TABLE_HOLDING, TABLE_INPUT):
                return await self.async_step_point_register()
            return await self.async_step_point_modbus()
        return self._form_with_back(await super().async_step_point_details(user_input))

    async def async_step_delete_point(self, user_input=None) -> ConfigFlowResult:
        """Allow return from point deletion confirmation."""
        if user_input is not None and user_input.get("back"):
            return await self.async_step_points()
        return self._form_with_back(await super().async_step_delete_point(user_input))

    async def async_step_bulk_move_select(self, user_input=None) -> ConfigFlowResult:
        """Select several points to move together."""
        points = await async_load_points(self.hass, self._entry.entry_id)
        options = [
            {
                "value": point["id"],
                "label": (
                    f"{point.get('section', '')} — {point.get('name', point['id'])}"
                ).lstrip(" —"),
            }
            for point in points
        ]
        schema = vol.Schema(
            {
                vol.Required("point_ids"): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("back", default=False): bool,
            }
        )
        if user_input is not None:
            if user_input.get("back"):
                return await self.async_step_points()
            selected = [str(item) for item in user_input.get("point_ids", [])]
            if not selected:
                return self.async_show_form(
                    step_id="bulk_move_select",
                    data_schema=schema,
                    errors={"base": "points_required"},
                )
            self._bulk_point_ids = selected
            return await self.async_step_bulk_move_section()
        return self.async_show_form(
            step_id="bulk_move_select",
            data_schema=schema,
        )

    async def async_step_bulk_move_section(self, user_input=None) -> ConfigFlowResult:
        """Choose the destination section/subsection."""
        points = await async_load_points(self.hass, self._entry.entry_id)
        schema = vol.Schema(
            {
                vol.Required("section_choice", default=SECTION_ROOT): self._section_selector(
                    points, ""
                ),
                vol.Optional("back", default=False): bool,
            }
        )
        if user_input is not None:
            if user_input.get("back"):
                return await self.async_step_bulk_move_select()
            choice = str(user_input["section_choice"])
            if choice == SECTION_NEW:
                return await self.async_step_bulk_new_section()
            destination = "" if choice == SECTION_ROOT else normalize_section_path(choice)
            return await self._apply_bulk_section(destination)
        return self.async_show_form(
            step_id="bulk_move_section",
            data_schema=schema,
        )

    async def async_step_bulk_new_section(self, user_input=None) -> ConfigFlowResult:
        """Create a new destination section/subsection."""
        points = await async_load_points(self.hass, self._entry.entry_id)
        paths = section_paths_from_points(points)
        parent_options = {SECTION_ROOT: "Aucune — section racine"}
        parent_options.update({path: path for path in paths})
        schema = vol.Schema(
            {
                vol.Required("parent_section", default=SECTION_ROOT): select(parent_options),
                vol.Required("section_name"): TextSelector(TextSelectorConfig()),
                vol.Optional("back", default=False): bool,
            }
        )
        if user_input is not None:
            if user_input.get("back"):
                return await self.async_step_bulk_move_section()
            name = normalize_section_path(user_input["section_name"])
            if not name:
                return self.async_show_form(
                    step_id="bulk_new_section",
                    data_schema=schema,
                    errors={"base": "section_required"},
                )
            parent = str(user_input["parent_section"])
            destination = (
                name
                if parent == SECTION_ROOT
                else normalize_section_path(f"{parent} / {name}")
            )
            return await self._apply_bulk_section(destination)
        return self.async_show_form(
            step_id="bulk_new_section",
            data_schema=schema,
        )

    async def _apply_bulk_section(self, destination: str) -> ConfigFlowResult:
        """Apply a section path to all selected point IDs."""
        points = await async_load_points(self.hass, self._entry.entry_id)
        selected = set(getattr(self, "_bulk_point_ids", []))
        changed = 0
        for point in points:
            if point.get("id") in selected:
                point["section"] = normalize_section_path(destination)
                changed += 1
        if not changed:
            return await self.async_step_bulk_move_select()
        await async_save_points(self.hass, self._entry.entry_id, points)
        return self._finish_points_change()
