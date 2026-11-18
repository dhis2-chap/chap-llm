"""Anonymize location names before anything is sent to an external LLM.

Replaces real district/location names with neutral placeholders
("District A", "District B", ...). The mapping is deterministic within
one call so the same location always gets the same placeholder.
"""

from __future__ import annotations


def anonymize_locations(location_names: list[str]) -> dict[str, str]:
    """Return a mapping from real location name to anonymous placeholder.

    Args:
        location_names: List of real location names from the contract.

    Returns:
        Dict mapping each name to a placeholder, e.g.
        {"Vientiane": "District A", "Attapeu": "District B"}.
        Names are sorted before assigning labels so the mapping is stable.
    """
    labels = _label_sequence(len(location_names))
    return {name: label for name, label in zip(sorted(location_names), labels)}


def _label_sequence(n: int) -> list[str]:
    """Generate n labels: District A, District B, ..., District Z,
    District AA, District AB, ... (Excel-column style)."""
    labels = []
    i = 0
    while len(labels) < n:
        label = _index_to_letters(i)
        labels.append(f"District {label}")
        i += 1
    return labels


def _index_to_letters(i: int) -> str:
    """Convert 0-based index to A, B, ..., Z, AA, AB, ..."""
    result = ""
    i += 1  # 1-based
    while i > 0:
        i, remainder = divmod(i - 1, 26)
        result = chr(65 + remainder) + result
    return result
