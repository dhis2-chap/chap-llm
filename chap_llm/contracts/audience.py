from __future__ import annotations

from typing import Literal, get_args

# "district_health_officer" is the spelling used throughout ARCHITECTURE.md,
# README.md and the prompt filenames. This is the single place the value is defined.
Audience = Literal["epidemiologist", "district_health_officer", "decision_maker"]

AUDIENCES: tuple[str, ...] = get_args(Audience)


def validate_audience(audience: str) -> Audience:
    """Audience is always set by the caller, never inferred. Fail loudly."""
    if audience not in AUDIENCES:
        raise ValueError(f"Unknown audience {audience!r}. Expected one of {AUDIENCES}.")
    return audience  # type: ignore[return-value]
