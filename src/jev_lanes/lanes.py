"""Pure confidence-band selection, independent of providers and graph execution."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

Lane = Literal["auto", "llm", "human"]


def _validate_unit_interval(value: float, *, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number, excluding bool")
    if not 0 <= value <= 1 or not isfinite(value):
        raise ValueError(f"{name} must be finite and between 0 and 1")


@dataclass(frozen=True)
class Lanes:
    """Explicit thresholds satisfying ``0 <= llm < auto <= 1``.

    Values are confidence thresholds, not accuracy guarantees. Select them
    using domain-specific evaluation; no universal defaults are supplied.
    """

    auto: float
    llm: float

    def __post_init__(self) -> None:
        _validate_unit_interval(self.auto, name="auto")
        _validate_unit_interval(self.llm, name="llm")
        if self.llm >= self.auto:
            raise ValueError("thresholds must satisfy llm < auto")

    def lane_for(self, confidence: float) -> Lane:
        """Select a lane; this does not validate a route or execute a decision.

        Invalid or absent confidence is an error, never a low-confidence result.
        Provider failures require a separate execution policy.
        """
        _validate_unit_interval(confidence, name="confidence")
        if confidence >= self.auto:
            return "auto"
        if confidence >= self.llm:
            return "llm"
        return "human"
