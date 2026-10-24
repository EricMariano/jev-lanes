"""Small validation helpers shared by the public modules."""

from __future__ import annotations

from math import isfinite


def validate_unit_interval(value: float, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number, excluding bool")
    if not 0 <= value <= 1 or not isfinite(value):
        raise ValueError(f"{name} must be finite and between 0 and 1")


def validate_name(value: object, *, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value:
        raise ValueError(f"{name} must not be empty")
