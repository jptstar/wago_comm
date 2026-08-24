"""Point decoding, encoding and helpers."""

from __future__ import annotations

import re
import struct
from typing import Any

from .const import (
    BYTE_BIG,
    DATA_BOOL,
    DATA_FLOAT32,
    DATA_INT16,
    DATA_INT32,
    DATA_UINT16,
    DATA_UINT32,
    TABLE_COIL,
    TABLE_DISCRETE,
    WORD_BIG,
)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def register_count(data_type: str) -> int:
    return 2 if data_type in (DATA_UINT32, DATA_INT32, DATA_FLOAT32) else 1


def _register_bytes(registers: list[int], byte_order: str, word_order: str) -> bytes:
    words = list(registers)
    if word_order != WORD_BIG and len(words) > 1:
        words.reverse()
    chunks: list[bytes] = []
    for word in words:
        chunk = int(word & 0xFFFF).to_bytes(2, "big")
        if byte_order != BYTE_BIG:
            chunk = chunk[::-1]
        chunks.append(chunk)
    return b"".join(chunks)


def decode_registers(registers: list[int], point: dict[str, Any]) -> int | float:
    data_type = point.get("data_type", DATA_UINT16)
    raw = _register_bytes(
        registers,
        point.get("byte_order", BYTE_BIG),
        point.get("word_order", WORD_BIG),
    )
    formats = {
        DATA_UINT16: ">H",
        DATA_INT16: ">h",
        DATA_UINT32: ">I",
        DATA_INT32: ">i",
        DATA_FLOAT32: ">f",
    }
    if data_type == DATA_BOOL:
        value: int | float = 1 if registers[0] else 0
    else:
        value = struct.unpack(formats.get(data_type, ">H"), raw)[0]
    bit = point.get("bit")
    if bit is not None:
        value = (int(value) >> int(bit)) & 1
    return value


def raw_point_value(data: dict[str, dict[int, Any]], point: dict[str, Any]) -> Any:
    table = point["table"]
    address = int(point["address"])
    values = data.get(table, {})
    if table in (TABLE_COIL, TABLE_DISCRETE):
        value = bool(values.get(address, False))
        return not value if point.get("inverted", False) else value

    count = register_count(point.get("data_type", DATA_UINT16))
    registers = [int(values.get(address + offset, 0)) for offset in range(count)]
    value = decode_registers(registers, point)
    if point.get("inverted", False) and point.get("bit") is not None:
        return not bool(value)
    return value


def decoded_point_value(data: dict[str, dict[int, Any]], point: dict[str, Any]) -> Any:
    raw = raw_point_value(data, point)
    if isinstance(raw, bool):
        return raw
    if point.get("platform") == "select":
        return raw
    scale = float(point.get("scale", 1.0) or 1.0)
    offset = float(point.get("offset", 0.0) or 0.0)
    value = float(raw) * scale + offset
    precision = point.get("precision")
    if precision is not None:
        value = round(value, int(precision))
    return value


def _pack_numeric(raw_value: int | float, point: dict[str, Any]) -> list[int]:
    data_type = point.get("data_type", DATA_UINT16)
    formats = {
        DATA_UINT16: ">H",
        DATA_INT16: ">h",
        DATA_UINT32: ">I",
        DATA_INT32: ">i",
        DATA_FLOAT32: ">f",
    }
    if data_type == DATA_BOOL:
        return [1 if raw_value else 0]
    packed = struct.pack(formats.get(data_type, ">H"), raw_value)
    words = [packed[i : i + 2] for i in range(0, len(packed), 2)]
    if point.get("byte_order", BYTE_BIG) != BYTE_BIG:
        words = [word[::-1] for word in words]
    if point.get("word_order", WORD_BIG) != WORD_BIG and len(words) > 1:
        words.reverse()
    return [int.from_bytes(word, "big") for word in words]


def encode_engineering_value(value: float, point: dict[str, Any]) -> list[int]:
    scale = float(point.get("scale", 1.0) or 1.0)
    offset = float(point.get("offset", 0.0) or 0.0)
    raw = (float(value) - offset) / scale
    data_type = point.get("data_type", DATA_UINT16)
    if data_type != DATA_FLOAT32:
        raw = int(round(raw))
    return _pack_numeric(raw, point)


def encode_raw_value(value: int | float, point: dict[str, Any]) -> list[int]:
    data_type = point.get("data_type", DATA_UINT16)
    if data_type != DATA_FLOAT32:
        value = int(round(value))
    return _pack_numeric(value, point)


def parse_select_options(value: str | dict[Any, Any] | None) -> dict[int, str]:
    if isinstance(value, dict):
        result: dict[int, str] = {}
        for key, label in value.items():
            try:
                result[int(key)] = str(label)
            except (TypeError, ValueError):
                continue
        return result
    result = {}
    for item in str(value or "").split("|"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        raw, label = item.split("=", 1)
        try:
            result[int(raw.strip())] = label.strip()
        except ValueError:
            continue
    return result
