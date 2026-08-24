"""CSV import/export helpers for configurable WAGO points."""

from __future__ import annotations

import csv
import io
from typing import Any

from .const import (
    DATA_BOOL,
    DATA_TYPES,
    DATA_UINT16,
    MAX_POINTS,
    PLATFORM_BUTTON,
    PLATFORM_NUMBER,
    PLATFORM_SELECT,
    PLATFORM_SWITCH,
    POINT_PLATFORMS,
    TABLE_COIL,
    TABLE_DISCRETE,
    TABLE_HOLDING,
    TABLE_INPUT,
    TABLES,
)
from .point import parse_select_options, register_count, slugify

CSV_FIELDS = [
    "enabled",
    "id",
    "section",
    "name",
    "platform",
    "table",
    "address",
    "data_type",
    "bit",
    "scale",
    "offset",
    "precision",
    "min",
    "max",
    "step",
    "unit",
    "device_class",
    "state_class",
    "read",
    "write",
    "inverted",
    "read_after_write",
    "byte_order",
    "word_order",
    "command_mode",
    "pulse_ms",
    "active_value",
    "return_value",
    "select_options",
    "icon",
    "notes",
]

TRUE_VALUES = {"1", "true", "yes", "oui", "on", "y"}
FALSE_VALUES = {"0", "false", "no", "non", "off", "n", ""}


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value if value is not None else "").strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return default


def _integer(value: Any, *, default: int | None = None) -> int:
    """Parse an integer while accepting spreadsheet forms such as 12.0 or 12,0."""
    text = str(value if value is not None else "").strip()
    if not text:
        if default is not None:
            return default
        raise ValueError("valeur entière vide")
    number = float(text.replace(",", "."))
    if not number.is_integer():
        raise ValueError(f"valeur entière attendue, reçu '{text}'")
    return int(number)


def _optional_int(value: Any) -> int | None:
    text = str(value if value is not None else "").strip()
    return None if not text else _integer(text)


def _optional_float(value: Any) -> float | None:
    text = str(value if value is not None else "").strip()
    return None if not text else float(text.replace(",", "."))


def _memory_range(memory: dict[str, tuple[int, int]], table: str) -> tuple[int, int]:
    start, size = memory[table]
    return start, start + size - 1


def normalize_point(row: dict[str, Any]) -> dict[str, Any]:
    platform = str(row.get("platform", "sensor")).strip().lower()
    table = str(row.get("table", TABLE_HOLDING)).strip().lower()
    name = str(row.get("name") or row.get("id") or "Point").strip()
    point_id = slugify(str(row.get("id") or name))
    data_type = str(
        row.get("data_type")
        or (DATA_BOOL if table in (TABLE_COIL, TABLE_DISCRETE) else DATA_UINT16)
    ).strip().lower()
    point: dict[str, Any] = {
        "enabled": _bool(row.get("enabled"), True),
        "id": point_id,
        "section": str(row.get("section") or "").strip(),
        "name": name,
        "platform": platform,
        "table": table,
        "address": _integer(row.get("address"), default=0),
        "data_type": data_type,
        "scale": _optional_float(row.get("scale")) or 1.0,
        "offset": _optional_float(row.get("offset")) or 0.0,
        "unit": str(row.get("unit") or "").strip(),
        "device_class": str(row.get("device_class") or "").strip(),
        "state_class": str(row.get("state_class") or "").strip(),
        "read": _bool(row.get("read"), platform != PLATFORM_BUTTON),
        "write": _bool(
            row.get("write"),
            platform in (PLATFORM_SWITCH, PLATFORM_NUMBER, PLATFORM_BUTTON, PLATFORM_SELECT),
        ),
        "inverted": _bool(row.get("inverted"), False),
        "read_after_write": _bool(row.get("read_after_write"), True),
        "byte_order": str(row.get("byte_order") or "big").strip().lower(),
        "word_order": str(row.get("word_order") or "big").strip().lower(),
        "command_mode": str(row.get("command_mode") or "pulse").strip().lower(),
        "pulse_ms": _optional_int(row.get("pulse_ms")) or 300,
        "active_value": _optional_float(row.get("active_value"))
        if str(row.get("active_value") or "").strip()
        else 1,
        "return_value": _optional_float(row.get("return_value"))
        if str(row.get("return_value") or "").strip()
        else 0,
        "select_options": str(row.get("select_options") or "").strip(),
        "icon": str(row.get("icon") or "").strip(),
        "notes": str(row.get("notes") or "").strip(),
    }
    for key, parser in (
        ("bit", _optional_int),
        ("precision", _optional_int),
        ("min", _optional_float),
        ("max", _optional_float),
        ("step", _optional_float),
    ):
        parsed = parser(row.get(key))
        if parsed is not None:
            point[key] = parsed
    return point


def validate_points(
    points: list[dict[str, Any]], memory: dict[str, tuple[int, int]]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if len(points) > MAX_POINTS:
        errors.append(f"{len(points)} points > limite de {MAX_POINTS}")

    ids: set[str] = set()
    addresses: dict[tuple[str, int, int | None], list[str]] = {}
    for index, point in enumerate(points, start=2):
        prefix = f"Ligne {index} ({point.get('name') or point.get('id')}): "
        point_id = str(point.get("id") or "")
        if not point_id:
            errors.append(prefix + "ID vide")
        elif point_id in ids:
            errors.append(prefix + f"ID dupliqué '{point_id}'")
        ids.add(point_id)

        platform = point.get("platform")
        table = point.get("table")
        if platform not in POINT_PLATFORMS:
            errors.append(prefix + f"plateforme inconnue '{platform}'")
        if table not in TABLES:
            errors.append(prefix + f"table Modbus inconnue '{table}'")
            continue
        if point.get("data_type") not in DATA_TYPES:
            errors.append(prefix + f"type de donnée inconnu '{point.get('data_type')}'")

        address = int(point.get("address", -1))
        start, end = _memory_range(memory, table)
        words = (
            register_count(point.get("data_type", DATA_UINT16))
            if table in (TABLE_HOLDING, TABLE_INPUT)
            else 1
        )
        if address < start or address + words - 1 > end:
            errors.append(prefix + f"adresse {address} hors plage {start}-{end}")

        bit = point.get("bit")
        if bit is not None:
            if table not in (TABLE_HOLDING, TABLE_INPUT):
                errors.append(prefix + "un bit n'est valide que sur un registre")
            elif not 0 <= int(bit) <= 15:
                errors.append(prefix + "bit doit être compris entre 0 et 15")

        if point.get("write") and table in (TABLE_DISCRETE, TABLE_INPUT):
            errors.append(prefix + f"{table} est en lecture seule")
        if (
            platform in (PLATFORM_SWITCH, PLATFORM_NUMBER, PLATFORM_BUTTON, PLATFORM_SELECT)
            and not point.get("write")
        ):
            warnings.append(prefix + "entité de commande sans écriture activée")
        if platform == PLATFORM_SELECT and not parse_select_options(point.get("select_options")):
            errors.append(prefix + "select_options est vide ou invalide")
        if float(point.get("scale", 1.0) or 0) == 0:
            errors.append(prefix + "scale ne peut pas être 0")
        if "min" in point and "max" in point and float(point["min"]) > float(point["max"]):
            errors.append(prefix + "min > max")
        if "step" in point and float(point["step"]) <= 0:
            errors.append(prefix + "step doit être > 0")

        key = (table, address, int(bit) if bit is not None else None)
        addresses.setdefault(key, []).append(point_id)

    for (table, address, bit), point_ids in addresses.items():
        if len(point_ids) > 1:
            suffix = f" bit {bit}" if bit is not None else ""
            warnings.append(
                f"{table} {address}{suffix} utilisé par plusieurs points: {', '.join(point_ids)}"
            )
    return errors, warnings


def parse_csv_text(
    text: str, memory: dict[str, tuple[int, int]]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    except csv.Error:
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        return [], ["En-tête CSV introuvable"], []
    required = {"id", "name", "platform", "table", "address"}
    missing = required - {str(field).strip() for field in reader.fieldnames}
    if missing:
        return [], [f"Colonnes manquantes: {', '.join(sorted(missing))}"], []
    points: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for line_number, row in enumerate(reader, start=2):
        if not any(str(value or "").strip() for value in row.values()):
            continue
        try:
            points.append(normalize_point(row))
        except (TypeError, ValueError) as err:
            parse_errors.append(f"Ligne {line_number}: {err}")
    errors, warnings = validate_points(points, memory)
    return points, parse_errors + errors, warnings


def export_csv_text(points: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=CSV_FIELDS,
        delimiter=";",
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for point in points:
        row = {field: point.get(field, "") for field in CSV_FIELDS}
        for field in ("enabled", "read", "write", "inverted", "read_after_write"):
            row[field] = "oui" if bool(point.get(field, False)) else "non"
        # Keep integer fields spreadsheet-friendly and round-trip safe.
        for field in ("address", "bit", "precision", "pulse_ms"):
            value = row.get(field)
            if value not in (None, ""):
                try:
                    number = float(str(value).replace(",", "."))
                except (TypeError, ValueError):
                    continue
                if number.is_integer():
                    row[field] = str(int(number))
        writer.writerow(row)
    return output.getvalue()
