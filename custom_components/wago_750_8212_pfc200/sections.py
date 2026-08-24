"""Section and subsection helpers for WAGO point devices."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
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


def section_key(path: str) -> str:
    """Return a comparison key insensitive to accents, punctuation, case and spaces."""
    normalized = normalize_section_path(path)
    if not normalized:
        return ""
    parts: list[str] = []
    for part in section_parts(normalized):
        ascii_text = "".join(
            char
            for char in unicodedata.normalize("NFKD", part.casefold())
            if not unicodedata.combining(char)
        )
        parts.append(re.sub(r"[^a-z0-9]+", "", ascii_text))
    return "/".join(parts)


def equivalent_section_path(candidate: str, paths: list[str]) -> str | None:
    """Find an existing section with the same punctuation/case-insensitive key."""
    key = section_key(candidate)
    if not key:
        return None
    for path in paths:
        if section_key(path) == key:
            return path
    return None


def similar_section_path(
    candidate: str, paths: list[str], *, threshold: float = 0.93
) -> str | None:
    """Find a very similar existing section, useful for catching spelling variants."""
    key = section_key(candidate)
    if not key:
        return None
    best_path: str | None = None
    best_ratio = 0.0
    for path in paths:
        other = section_key(path)
        if not other or other == key:
            continue
        ratio = SequenceMatcher(None, key, other).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_path = path
    return best_path if best_ratio >= threshold else None


def section_point_count(points: list[dict[str, Any]], path: str) -> int:
    """Count points directly in a section or any of its subsections."""
    normalized = normalize_section_path(path)
    prefix = f"{normalized}{SECTION_SEPARATOR}" if normalized else ""
    return sum(
        1
        for point in points
        if (section := normalize_section_path(point.get("section", "")))
        and (section == normalized or section.startswith(prefix))
    )


def replace_section_prefix(section: str, source: str, destination: str) -> str:
    """Replace a section subtree prefix while preserving child paths."""
    current = normalize_section_path(section)
    source = normalize_section_path(source)
    destination = normalize_section_path(destination)
    if not source or (current != source and not current.startswith(f"{source}{SECTION_SEPARATOR}")):
        return current
    suffix = current[len(source) :].lstrip(" /")
    if not destination:
        return normalize_section_path(suffix)
    if not suffix:
        return destination
    return normalize_section_path(f"{destination}{SECTION_SEPARATOR}{suffix}")
