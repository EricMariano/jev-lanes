"""Contract for the classifier.

The gate depends on this Protocol only, so any provider can be injected and tests need no
network. Provider failures (timeout, missing credential) must be raised, never mapped to a
low confidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from jev_lanes._validate import validate_unit_interval


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
        validate_unit_interval(self.confidence, name="confidence")


@runtime_checkable
class Classifier(Protocol):
    """Chooses one of ``routes`` (the customer's intents) for ``payload``.

    ``routes`` maps each intent name to its description (the criteria shown to the model).
    ``payload`` is whatever the caller's ``extract`` function produced from the graph state.
    """

    def classify(self, payload: object, routes: Mapping[str, str]) -> Classification: ...
