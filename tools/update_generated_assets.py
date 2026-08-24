#!/usr/bin/env python3
"""Refresh the reference WAGO profile and user-facing export text."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "examples" / "wago_points.csv"
JSON_PATHS = [
    ROOT / "custom_components" / "wago_750_8212_pfc200" / "strings.json",
    ROOT / "custom_components" / "wago_750_8212_pfc200" / "translations" / "fr.json",
]


def patch_texts() -> None:
    for path in JSON_PATHS:
        data = json.loads(path.read_text(encoding="utf-8"))
        options = data["options"]
        options["step"]["export_csv"]["description"] = (
            "Prépare un téléchargement direct du tableau actuel. Aucun fichier permanent "
            "n’est créé dans /config/www."
        )
        options["step"]["export_csv"]["data"]["confirm"] = "Préparer le téléchargement CSV"
        options["abort"]["export_ok"] = (
            "CSV prêt : {url}\n\nLe lien reste valable {path}. Un clic normal suffit."
        )
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def blank(fieldnames: list[str], **values: str) -> dict[str, str]:
    row = {key: "" for key in fieldnames}
    row.update(
        {
            "enabled": "oui",
            "scale": "1",
            "offset": "0",
            "read": "oui",
            "write": "non",
            "inverted": "non",
            "read_after_write": "oui",
            "byte_order": "big",
            "word_order": "big",
            "command_mode": "normal",
            "pulse_ms": "300",
            "active_value": "1",
            "return_value": "0",
        }
    )
    row.update(values)
    return row


def switch(fieldnames: list[str], ident: str, section: str, name: str, address: int, *, icon: str, notes: str) -> dict[str, str]:
    return blank(
        fieldnames,
        id=ident,
        section=section,
        name=name,
        platform="switch",
        table="coil",
        address=str(address),
        data_type="bool",
        write="oui",
        icon=icon,
        notes=notes,
    )


def number(fieldnames: list[str], ident: str, section: str, name: str, address: int, *, notes: str) -> dict[str, str]:
    return blank(
        fieldnames,
        id=ident,
        section=section,
        name=name,
        platform="number",
        table="holding_register",
        address=str(address),
        data_type="uint16",
        precision="0",
        min="0",
        max="600",
        step="1",
        unit="min",
        write="oui",
        icon="mdi:timer-cog",
        notes=notes,
    )


def sensor(fieldnames: list[str], ident: str, section: str, name: str, address: int, *, icon: str, notes: str) -> dict[str, str]:
    return blank(
        fieldnames,
        id=ident,
        section=section,
        name=name,
        platform="sensor",
        table="holding_register",
        address=str(address),
        data_type="uint16",
        precision="0",
        icon=icon,
        notes=notes,
    )


def binary_sensor(fieldnames: list[str], ident: str, section: str, name: str, address: int, *, icon: str, notes: str) -> dict[str, str]:
    return blank(
        fieldnames,
        id=ident,
        section=section,
        name=name,
        platform="binary_sensor",
        table="holding_register",
        address=str(address),
        data_type="uint16",
        icon=icon,
        notes=notes,
    )


def patch_profile() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    by_id = {row["id"]: row for row in rows}

    # CODESYS screenshots 2026-08-24 resolve the old duplicate Coil 21.
    if "drip_hedge_path_manual" in by_id:
        by_id["drip_hedge_path_manual"]["address"] = "34"
        by_id["drip_hedge_path_manual"]["notes"] = (
            "Confirmé CODESYS : Arrosage_GG.xCmd_GG_Manu[1] = Coil 34."
        )
    if "lawn_terrace_base_duration" in by_id:
        by_id["lawn_terrace_base_duration"]["max"] = "600"
        by_id["lawn_terrace_base_duration"]["notes"] = (
            "CODESYS : uiBaseDurationMin[1], plage 0–600 min."
        )
    if "pool_fill_valve_state" in by_id:
        by_id["pool_fill_valve_state"]["notes"] = (
            "Ancien mapping Node-RED DI56 ; non mappé sur les captures CODESYS du 24/08/2026 — à vérifier."
        )

    additions = [
        switch(fieldnames, "filter_pressure_delta_command", "Filtration puits", "Commande seuil pression différentielle", 6, icon="mdi:gauge", notes="CODESYS : mSet_PressionDifferentiel (Coil 6), fonction exacte à confirmer."),
        switch(fieldnames, "lawn_circuit5_manual", "Arrosage gazon", "Circuit gazon 5 — manuel", 22, icon="mdi:sprinkler", notes="CODESYS : xCmd_Manu[5]."),
        switch(fieldnames, "lawn_terrace_enabled", "Arrosage gazon", "Gazon terrasse — autorisé", 23, icon="mdi:sprinkler-variant", notes="CODESYS : xEnableCircuit[1]."),
        switch(fieldnames, "lawn_slope_enabled", "Arrosage gazon", "Gazon butte — autorisé", 24, icon="mdi:sprinkler-variant", notes="CODESYS : xEnableCircuit[2]."),
        switch(fieldnames, "lawn_pool_enabled", "Arrosage gazon", "Gazon piscine — autorisé", 25, icon="mdi:sprinkler-variant", notes="CODESYS : xEnableCircuit[3]."),
        switch(fieldnames, "lawn_poolhouse_enabled", "Arrosage gazon", "Gazon pool house — autorisé", 26, icon="mdi:sprinkler-variant", notes="CODESYS : xEnableCircuit[4]."),
        switch(fieldnames, "lawn_circuit5_enabled", "Arrosage gazon", "Circuit gazon 5 — autorisé", 27, icon="mdi:sprinkler-variant", notes="CODESYS : xEnableCircuit[5]."),
        switch(fieldnames, "lawn_reverse_order", "Arrosage gazon", "Inverser l’ordre des circuits", 28, icon="mdi:swap-vertical", notes="CODESYS : xReverseOrder."),
        switch(fieldnames, "lawn_resume_after_manual", "Arrosage gazon", "Reprendre le cycle après manuel", 29, icon="mdi:play-circle-outline", notes="CODESYS : xResumeAfterManual."),
        number(fieldnames, "lawn_slope_base_duration", "Arrosage gazon", "Durée de base gazon butte", 71, notes="CODESYS : uiBaseDurationMin[2]."),
        number(fieldnames, "lawn_pool_base_duration", "Arrosage gazon", "Durée de base gazon piscine", 72, notes="CODESYS : uiBaseDurationMin[3]."),
        number(fieldnames, "lawn_poolhouse_base_duration", "Arrosage gazon", "Durée de base gazon pool house", 73, notes="CODESYS : uiBaseDurationMin[4]."),
        number(fieldnames, "lawn_circuit5_base_duration", "Arrosage gazon", "Durée de base circuit gazon 5", 74, notes="CODESYS : uiBaseDurationMin[5]."),
        sensor(fieldnames, "lawn_mode", "Arrosage gazon", "Mode", 77, icon="mdi:state-machine", notes="CODESYS : uiStatus_Mode."),
        sensor(fieldnames, "lawn_cycles_done", "Arrosage gazon", "Cycles effectués", 79, icon="mdi:counter", notes="CODESYS : uiStatus_CyclesDone."),
        binary_sensor(fieldnames, "lawn_active", "Arrosage gazon", "Arrosage actif", 81, icon="mdi:sprinkler", notes="CODESYS : uiStatus_Active."),
        switch(fieldnames, "drip_circuit2_manual", "Arrosage goutte-à-goutte", "Circuit GG 2 — manuel", 35, icon="mdi:water-outline", notes="CODESYS : xCmd_GG_Manu[2]."),
        switch(fieldnames, "drip_circuit3_manual", "Arrosage goutte-à-goutte", "Circuit GG 3 — manuel", 36, icon="mdi:water-outline", notes="CODESYS : xCmd_GG_Manu[3]."),
        switch(fieldnames, "drip_circuit4_manual", "Arrosage goutte-à-goutte", "Circuit GG 4 — manuel", 37, icon="mdi:water-outline", notes="CODESYS : xCmd_GG_Manu[4]."),
        switch(fieldnames, "drip_circuit5_manual", "Arrosage goutte-à-goutte", "Circuit GG 5 — manuel", 38, icon="mdi:water-outline", notes="CODESYS : xCmd_GG_Manu[5]."),
        switch(fieldnames, "drip_hedge_path_enabled", "Arrosage goutte-à-goutte", "Haies chemin — autorisé", 39, icon="mdi:water-check-outline", notes="CODESYS : xEnableGG[1]."),
        number(fieldnames, "drip_hedge_path_base_duration", "Arrosage goutte-à-goutte", "Durée de base haies chemin", 82, notes="CODESYS : uiGG_BaseDurationMin[1]."),
        number(fieldnames, "drip_circuit2_base_duration", "Arrosage goutte-à-goutte", "Durée de base circuit GG 2", 83, notes="CODESYS : uiGG_BaseDurationMin[2]."),
        number(fieldnames, "drip_circuit3_base_duration", "Arrosage goutte-à-goutte", "Durée de base circuit GG 3", 84, notes="CODESYS : uiGG_BaseDurationMin[3]."),
        number(fieldnames, "drip_circuit4_base_duration", "Arrosage goutte-à-goutte", "Durée de base circuit GG 4", 85, notes="CODESYS : uiGG_BaseDurationMin[4]."),
        number(fieldnames, "drip_circuit5_base_duration", "Arrosage goutte-à-goutte", "Durée de base circuit GG 5", 86, notes="CODESYS : uiGG_BaseDurationMin[5]."),
        sensor(fieldnames, "drip_mode", "Arrosage goutte-à-goutte", "Mode", 89, icon="mdi:state-machine", notes="CODESYS : uiGG_Status_Mode."),
        sensor(fieldnames, "drip_cycles_done", "Arrosage goutte-à-goutte", "Cycles effectués", 91, icon="mdi:counter", notes="CODESYS : uiGG_Status_CyclesDone."),
        binary_sensor(fieldnames, "drip_active", "Arrosage goutte-à-goutte", "Goutte-à-goutte actif", 93, icon="mdi:water-check", notes="CODESYS : uiGG_Status_Active."),
    ]

    existing_ids = set(by_id)
    rows.extend(item for item in additions if item["id"] not in existing_ids)

    order = {"coil": 0, "discrete_input": 1, "holding_register": 2, "input_register": 3}

    def address(row: dict[str, str]) -> int:
        try:
            return int(float(row.get("address", "")))
        except (TypeError, ValueError):
            return 999999

    rows.sort(key=lambda row: (order.get(row.get("table", ""), 9), address(row), row.get("id", "")))
    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    patch_texts()
    patch_profile()
