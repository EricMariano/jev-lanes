"""Deterministic fakes for tests: no network, no credentials, no provider calls."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

from jev_lanes.protocols import Classification

T = TypeVar("T")


@dataclass(frozen=True)
class Call:
    """One recorded call: the payload received and a snapshot of the routes."""

    payload: object
    routes: Mapping[str, str]


class _Scripted(Generic[T]):
    """Plays scripted results in order; an ``Exception`` in the script is raised."""

    def __init__(self, results: tuple[T | Exception, ...]) -> None:
        self._results = list(results)
        self.calls: list[Call] = []

    def _next(self, payload: object, routes: Mapping[str, str]) -> T:
        self.calls.append(Call(payload, dict(routes)))
        if not self._results:
            raise RuntimeError(f"{type(self).__name__} has no scripted result left")
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeJevClassifier(_Scripted[Classification]):
    """Classifier that returns scripted ``Classification`` objects in order.

    Pass an ``Exception`` to simulate a provider failure. ``calls`` records every call, so
    tests can prove that a resumed human review did not classify again.
    """

    def __init__(self, *results: Classification | Exception) -> None:
        super().__init__(results)

    def classify(self, payload: object, routes: Mapping[str, str]) -> Classification:
        return self._next(payload, routes)


class FakeFallback(_Scripted[str | None]):
    """Fallback model that returns scripted route names (``None`` abstains) in order."""

    def __init__(self, *results: str | None | Exception) -> None:
        super().__init__(results)

    def decide(self, payload: object, routes: Mapping[str, str]) -> str | None:
        return self._next(payload, routes)
