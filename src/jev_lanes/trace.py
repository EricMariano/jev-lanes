"""Serializable record of what the gate decided during one turn.

The trace stores which tool calls were checked against which classification, and how many
clarification rounds were spent. It never stores the case text, tool arguments or model
output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, get_args

from jev_lanes._validate import validate_name, validate_unit_interval

CheckOutcome = Literal["allowed", "low_confidence", "intent_mismatch"]


@dataclass(frozen=True)
class Check:
    """One tool call checked against the classifier's reading of the conversation.

    ``intent`` and ``confidence`` come from the classifier; ``required`` is the tool's
    minimum confidence. ``intent_mismatch`` means the classified intent is not one the tool
    serves, whatever the confidence; it takes precedence over ``low_confidence``.
    """

    tool: str
    intent: str
    confidence: float
    required: float
    outcome: CheckOutcome

    def __post_init__(self) -> None:
        validate_name(self.tool, name="tool")
        validate_name(self.intent, name="intent")
        validate_unit_interval(self.confidence, name="confidence")
        validate_unit_interval(self.required, name="required")
        if self.outcome not in get_args(CheckOutcome):
            raise ValueError(f"outcome must be one of {get_args(CheckOutcome)}")
        if self.outcome == "allowed" and self.confidence < self.required:
            raise ValueError("an allowed check needs confidence >= required")
        if self.outcome == "low_confidence" and self.confidence >= self.required:
            raise ValueError("a low_confidence check needs confidence < required")

    @property
    def allowed(self) -> bool:
        return self.outcome == "allowed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "intent": self.intent,
            "confidence": self.confidence,
            "required": self.required,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Check:
        _check_keys(data, {"tool", "intent", "confidence", "required", "outcome"}, what="check")
        return cls(
            tool=data["tool"],
            intent=data["intent"],
            confidence=data["confidence"],
            required=data["required"],
            outcome=data["outcome"],
        )


@dataclass(frozen=True)
class GateTrace:
    """Checks made in one turn, in order, plus the clarification rounds spent.

    ``refused`` is set when the turn ended without the customer's request being served
    because clarification did not reach the required confidence.
    """

    checks: tuple[Check, ...] = ()
    clarifications: int = 0
    refused: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "checks", tuple(self.checks))
        if not all(isinstance(item, Check) for item in self.checks):
            raise TypeError("checks must contain Check objects")
        if isinstance(self.clarifications, bool) or not isinstance(self.clarifications, int):
            raise TypeError("clarifications must be an int")
        if self.clarifications < 0:
            raise ValueError("clarifications must not be negative")
        if not isinstance(self.refused, bool):
            raise TypeError("refused must be a bool")
        if self.refused and (not self.checks or self.checks[-1].allowed):
            raise ValueError("a refused turn must end with a check that was not allowed")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return {
            "checks": [item.to_dict() for item in self.checks],
            "clarifications": self.clarifications,
            "refused": self.refused,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GateTrace:
        _check_keys(data, {"checks", "clarifications", "refused"}, what="trace")
        return cls(
            checks=tuple(Check.from_dict(item) for item in data["checks"]),
            clarifications=data["clarifications"],
            refused=data["refused"],
        )


def _check_keys(data: Mapping[str, Any], allowed: set[str], *, what: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown {what} keys: {sorted(unknown)}")
