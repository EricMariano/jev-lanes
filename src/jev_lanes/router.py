"""``JevRouter``: applies the lane policy to a LangGraph ``StateGraph``.

Three nodes are added per router: classification, the fallback model, and a human review
that calls ``interrupt()``. Classification runs in its own node, so resuming the human
review never classifies again (see ADR 0002). Everything the router stores in the graph
state lives under one key, ``state_key``, as ``RouteTrace.to_dict()``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from langgraph.graph import StateGraph
from langgraph.types import interrupt

from jev_lanes.lanes import Lanes
from jev_lanes.protocols import Classifier, FallbackModel
from jev_lanes.trace import EscalationReason, Evaluation, RouteTrace

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


def default_extract(state: Mapping[str, Any]) -> object:
    """Send the state's ``messages`` to the classifier and the fallback model."""
    try:
        return state["messages"]
    except KeyError:
        raise ValueError(
            "the graph state has no 'messages'; pass extract=... to JevRouter "
            "to choose what is sent to the providers"
        ) from None


@dataclass(frozen=True, eq=False)
class JevRouter:
    """Routes a case by Jev confidence, with a fallback model and human review.

    ``routes`` maps each route name to its description. ``extract`` receives the graph
    state and returns the payload sent to the classifier and the fallback model; use it to
    restrict or redact what leaves your environment. The graph state schema must declare
    the key ``state_key``.
    """

    name: str
    routes: Mapping[str, str]
    lanes: Lanes
    classifier: Classifier
    fallback: FallbackModel
    extract: Callable[[Mapping[str, Any]], object] = default_extract

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME.match(self.name):
            raise ValueError("name must start with a letter and contain only letters, digits, _")
        if not self.routes:
            raise ValueError("routes must not be empty")
        if not all(isinstance(k, str) and k for k in self.routes):
            raise ValueError("route names must be non-empty strings")
        if not all(isinstance(v, str) for v in self.routes.values()):
            raise TypeError("route descriptions must be strings")
        object.__setattr__(self, "routes", MappingProxyType(dict(self.routes)))
        if not isinstance(self.lanes, Lanes):
            raise TypeError("lanes must be a Lanes instance")
        if not isinstance(self.classifier, Classifier):
            raise TypeError("classifier must provide classify(payload, routes)")
        if not isinstance(self.fallback, FallbackModel):
            raise TypeError("fallback must provide decide(payload, routes)")
        if not callable(self.extract):
            raise TypeError("extract must be callable")

    @property
    def state_key(self) -> str:
        return f"{self.name}_route"

    @property
    def classify_node(self) -> str:
        return f"{self.name}_classify"

    @property
    def llm_node(self) -> str:
        return f"{self.name}_llm"

    @property
    def human_node(self) -> str:
        return f"{self.name}_human"

    def classify(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Ask the classifier and select a lane. Starts a new episode in the state."""
        result = self.classifier.classify(self.extract(state), self.routes)
        if result.route not in self.routes:
            raise ValueError(f"classifier returned unknown route {result.route!r}")
        lane = self.lanes.lane_for(result.confidence)
        trace = RouteTrace(
            lane,
            (Evaluation("jev", result.route, confidence=result.confidence),),
            final_route=result.route if lane == "auto" else None,
        )
        return {self.state_key: trace.to_dict()}

    def llm(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Ask the fallback model. Abstaining or naming an unknown route needs human review."""
        trace = self._load(state)
        route = self.fallback.decide(self.extract(state), self.routes)
        evaluation = Evaluation("llm", route, reason="low_confidence")
        accepted = route if route in self.routes else None
        updated = RouteTrace(trace.lane, (*trace.evaluations, evaluation), accepted)
        return {self.state_key: updated.to_dict()}

    def human(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Pause for a human to pick a route; ``Command(resume="<route>")`` resumes.

        The surfaced value holds the suggestions so far, never the case text; read the case
        from the graph state. An unknown route is rejected by LangGraph and can be re-sent.
        """
        trace = self._load(state)
        last = trace.evaluations[-1]
        reason: EscalationReason = "low_confidence"
        if last.evaluator == "llm":
            reason = "llm_abstained" if last.route is None else "llm_invalid_route"
        review = {
            "router": self.name,
            "reason": reason,
            "routes": dict(self.routes),
            "suggestions": [item.to_dict() for item in trace.evaluations],
        }
        route = interrupt(review, response_schema=Literal[tuple(self.routes)])  # type: ignore[misc]
        evaluation = Evaluation("human", route, reason=reason)
        updated = RouteTrace(trace.lane, (*trace.evaluations, evaluation), route)
        return {self.state_key: updated.to_dict()}

    def attach(
        self,
        builder: StateGraph,
        *,
        after: str,
        targets: Mapping[str, str] | None = None,
    ) -> None:
        """Add the router's nodes and edges to ``builder``, running after node ``after``.

        ``targets`` maps every route name to the node that handles it; by default a route
        name is also its node name. Add the target nodes to ``builder`` yourself.
        """
        mapping = {route: route for route in self.routes} if targets is None else dict(targets)
        if set(mapping) != set(self.routes):
            raise ValueError("targets must map exactly the router's routes")

        def next_node(state: Mapping[str, Any]) -> str:
            trace = self._load(state)
            if trace.final_route is not None:
                return mapping[trace.final_route]
            if trace.evaluations[-1].evaluator == "jev" and trace.lane == "llm":
                return self.llm_node
            return self.human_node

        builder.add_node(self.classify_node, self.classify)
        builder.add_node(self.llm_node, self.llm)
        builder.add_node(self.human_node, self.human)
        builder.add_edge(after, self.classify_node)
        destinations = [self.llm_node, self.human_node, *dict.fromkeys(mapping.values())]
        for node in (self.classify_node, self.llm_node, self.human_node):
            builder.add_conditional_edges(node, next_node, destinations)

    def _load(self, state: Mapping[str, Any]) -> RouteTrace:
        try:
            data = state[self.state_key]
        except KeyError:
            raise ValueError(f"the graph state has no {self.state_key!r} key") from None
        return RouteTrace.from_dict(data)
