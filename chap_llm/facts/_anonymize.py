from __future__ import annotations

from collections.abc import Sequence


def _letters(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, 27 -> AB, ... (spreadsheet-style)."""
    out = ""
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(ord("A") + rem) + out
    return out


def location_aliases(locations: Sequence[str]) -> dict[str, str]:
    """Map real location names to stable placeholders ("District A", ...).

    Deterministic: the same sorted input always gives the same mapping, so the
    caller (e.g. the frontend) can recompute it to de-anonymize the response.
    The mapping itself is never part of the facts sent to an LLM.
    """
    return {loc: f"District {_letters(i)}" for i, loc in enumerate(sorted(set(locations)))}
