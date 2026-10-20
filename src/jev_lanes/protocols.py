"""Contracts for the classifier and the fallback model.

The policy depends on these Protocols only, so any provider can be injected and tests need
no network. Provider failures (timeout, missing credential) must be raised, never mapped to
a low confidence or an abstention.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from jev_lanes.lanes import _validate_unit_interval


@dataclass(frozen=True)
class Classification:
    """A classifier's chosen route and its confidence in ``[0, 1]``.

    Confidence is a distribution statistic, not an accuracy guarantee.
    """

    route: str
    confidence: float

    def __post_init__(self) -> None:
        if not isinstance(self.route, str):
            raise TypeError("route must be a string")
        if not self.route:
            raise ValueError("route must not be empty")
        _validate_unit_interval(self.confidence, name="confidence")


@runtime_checkable
class Classifier(Protocol):
    """Chooses one of ``routes`` for ``payload``.

    ``routes`` maps each route name to its description (the criteria shown to the model).
    ``payload`` is whatever the caller's ``extract`` function produced from the graph state.
    """

    def classify(self, payload: object, routes: Mapping[str, str]) -> Classification: ...


@runtime_checkable
class FallbackModel(Protocol):
    """Re-evaluates a case the classifier was not confident about.

    Returns a route name, or ``None`` to abstain. The router checks that the name is one of
    ``routes``; an abstention or an unknown name escalates to human review.
    """

    def decide(self, payload: object, routes: Mapping[str, str]) -> str | None: ...
