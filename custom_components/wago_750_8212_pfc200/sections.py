"""Section and subsection helpers for WAGO point devices."""

from __future__ import annotations

from typing import Any

from .point import slugify

SECTION_SEPARATOR = " / "


def normalize_section_path(value: Any) -> str:
    """Normalize a user-facing hierarchical section path."""
    text = str(value or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.replace(">", "/").split("/")]
    return SECTION_SEPARATOR.join(part for part in parts if part)


def section_parts(path: str) -> list[str]:
    """Return normalized path components."""
    normalized = normalize_section_path(path)
    return normalized.split(SECTION_SEPARATOR) if normalized else []


def section_parent(path: str) -> str:
    """Return the parent section path, or an empty string for a root section."""
    parts = section_parts(path)
    return SECTION_SEPARATOR.join(parts[:-1]) if len(parts) > 1 else ""


def section_leaf(path: str) -> str:
    """Return the displayed leaf name."""
    parts = section_parts(path)
    return parts[-1] if parts else ""


def section_identifier(entry_id: str, path: str) -> str:
    """Return the stable device identifier used by Home Assistant."""
    normalized = normalize_section_path(path)
    return f"{entry_id}:{slugify(normalized) or 'points'}"


def section_paths_from_points(points: list[dict[str, Any]]) -> list[str]:
    """Return every used section and parent subsection in display order."""
    paths: set[str] = set()
    for point in points:
        parts = section_parts(str(point.get("section") or ""))
        for index in range(1, len(parts) + 1):
            paths.add(SECTION_SEPARATOR.join(parts[:index]))
    return sorted(paths, key=lambda item: (item.count(SECTION_SEPARATOR), item.casefold()))
