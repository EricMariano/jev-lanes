"""Serializable record of a routing episode.

The trace stores who evaluated a case and what they suggested. It never stores the case
text or raw provider payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, get_args

from jev_lanes.lanes import Lane, _validate_unit_interval

Evaluator = Literal["jev", "llm", "human"]
EscalationReason = Literal["low_confidence", "llm_abstained", "llm_invalid_route"]

# Evaluator sequences a trace may hold for each entry lane. A prefix is a trace that is
# still waiting for the next evaluator (for example, persisted before a human review).
_SEQUENCES: dict[str, tuple[tuple[str, ...], ...]] = {
    "auto": (("jev",),),
    "llm": (("jev",), ("jev", "llm"), ("jev", "llm", "human")),
    "human": (("jev",), ("jev", "human")),
}


def _check_route(route: object, *, name: str) -> None:
    if not isinstance(route, str):
        raise TypeError(f"{name} must be a string")
    if not route:
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class Evaluation:
    """One evaluator's suggestion.

    ``route`` is the suggestion exactly as returned, so it may be an invalid route name;
    only the LLM may abstain (``route=None``). ``confidence`` is recorded for Jev only.
    ``reason`` says why this evaluator was consulted and is ``None`` for the first Jev call.
    """

    evaluator: Evaluator
    route: str | None
    confidence: float | None = None
    reason: EscalationReason | None = None

    def __post_init__(self) -> None:
        if self.evaluator not in get_args(Evaluator):
            raise ValueError(f"evaluator must be one of {get_args(Evaluator)}")
        if self.route is None:
            if self.evaluator != "llm":
                raise ValueError("only the llm evaluator may abstain")
        else:
            _check_route(self.route, name="route")
        if self.evaluator == "jev":
            if self.confidence is None:
                raise ValueError("a jev evaluation requires confidence")
            _validate_unit_interval(self.confidence, name="confidence")
            if self.reason is not None:
                raise ValueError("a jev evaluation is never an escalation")
        else:
            if self.confidence is not None:
                raise ValueError("only jev evaluations record confidence")
            if self.reason is None:
                raise ValueError(f"a {self.evaluator} evaluation requires a reason")
        if self.reason is not None and self.reason not in get_args(EscalationReason):
            raise ValueError(f"reason must be one of {get_args(EscalationReason)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator": self.evaluator,
            "route": self.route,
            "confidence": self.confidence,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Evaluation:
        _check_keys(data, {"evaluator", "route", "confidence", "reason"}, what="evaluation")
        return cls(
            evaluator=data["evaluator"],
            route=data["route"],
            confidence=data.get("confidence"),
            reason=data.get("reason"),
        )


@dataclass(frozen=True)
class RouteTrace:
    """Evaluations of one routing episode, in order, plus the final route once decided.

    ``lane`` is the entry lane selected from Jev's confidence. ``final_route`` is ``None``
    until a decision is accepted, so the trace can be persisted before escalating.
    """

    lane: Lane
    evaluations: tuple[Evaluation, ...]
    final_route: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluations", tuple(self.evaluations))
        if self.lane not in _SEQUENCES:
            raise ValueError(f"lane must be one of {tuple(_SEQUENCES)}")
        if not all(isinstance(item, Evaluation) for item in self.evaluations):
            raise TypeError("evaluations must contain Evaluation objects")
        self._validate_sequence()
        self._validate_final_route()

    def _validate_sequence(self) -> None:
        sequence = tuple(item.evaluator for item in self.evaluations)
        if sequence not in _SEQUENCES[self.lane]:
            raise ValueError(f"evaluators {sequence} are not valid for lane {self.lane!r}")
        for index, item in enumerate(self.evaluations[1:], start=1):
            previous = self.evaluations[index - 1]
            if item.evaluator == "llm" or previous.evaluator == "jev":
                expected: tuple[str, ...] = ("low_confidence",)
            else:
                expected = ("llm_abstained", "llm_invalid_route")
            if item.reason not in expected:
                raise ValueError(f"reason {item.reason!r} is invalid for {item.evaluator} here")
            if item.reason == "llm_abstained" and previous.route is not None:
                raise ValueError("llm_abstained requires an abstaining llm evaluation")
            if item.reason == "llm_invalid_route" and previous.route is None:
                raise ValueError("llm_invalid_route requires an llm route")

    def _validate_final_route(self) -> None:
        if self.final_route is None:
            return
        _check_route(self.final_route, name="final_route")
        last = self.evaluations[-1]
        if last.evaluator == "jev" and self.lane != "auto":
            raise ValueError("a jev suggestion is accepted only in the auto lane")
        if self.final_route != last.route:
            raise ValueError("final_route must be the last evaluation's route")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""
        return {
            "lane": self.lane,
            "evaluations": [item.to_dict() for item in self.evaluations],
            "final_route": self.final_route,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RouteTrace:
        _check_keys(data, {"lane", "evaluations", "final_route"}, what="trace")
        return cls(
            lane=data["lane"],
            evaluations=tuple(Evaluation.from_dict(item) for item in data["evaluations"]),
            final_route=data.get("final_route"),
        )


def _check_keys(data: Mapping[str, Any], allowed: set[str], *, what: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown {what} keys: {sorted(unknown)}")
