"""Explicit graph wiring equivalent to ``router.attach()``.

Run ``uv run python examples/manual_routing.py``. The node implementations are the
same; only the edges are written manually. See tests/test_manual_equivalence.py.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from jev_lanes import Classification, JevRouter, Lanes, RouteTrace
from jev_lanes.testing import FakeFallback, FakeJevClassifier


def wire_manually(
    builder: StateGraph,
    router: JevRouter,
    *,
    after: str,
    targets: Mapping[str, str] | None = None,
) -> None:
    """Expand the graph topology, reusing the router's public node methods."""
    mapping = dict(targets) if targets is not None else {route: route for route in router.routes}
    if set(mapping) != set(router.routes):
        raise ValueError("targets must map exactly the router's routes")

    def after_classify(state: Mapping[str, Any]) -> str:
        trace = RouteTrace.from_dict(state[router.state_key])
        if trace.final_route is not None:
            return mapping[trace.final_route]
        return router.llm_node if trace.lane == "llm" else router.human_node

    def after_fallback(state: Mapping[str, Any]) -> str:
        trace = RouteTrace.from_dict(state[router.state_key])
        return mapping[trace.final_route] if trace.final_route is not None else router.human_node

    def after_human(state: Mapping[str, Any]) -> str:
        trace = RouteTrace.from_dict(state[router.state_key])
        return mapping[trace.final_route]

    builder.add_node(router.classify_node, router.classify)
    builder.add_node(router.llm_node, router.llm)
    builder.add_node(router.human_node, router.human)
    builder.add_edge(after, router.classify_node)
    destinations = list(dict.fromkeys(mapping.values()))
    builder.add_conditional_edges(
        router.classify_node, after_classify, [router.llm_node, router.human_node, *destinations]
    )
    builder.add_conditional_edges(
        router.llm_node, after_fallback, [router.human_node, *destinations]
    )
    builder.add_conditional_edges(router.human_node, after_human, destinations)


def main() -> None:
    class State(TypedDict, total=False):
        messages: list[str]
        support_route: dict[str, Any]
        handled_by: str

    for wiring in (wire_manually, lambda builder, router, **kw: router.attach(builder, **kw)):
        router = JevRouter(
            name="support",
            routes={"orders": "Delivery", "billing": "Payments"},
            lanes=Lanes(auto=0.85, llm=0.60),
            classifier=FakeJevClassifier(Classification("orders", 0.70)),
            fallback=FakeFallback(None),
        )
        builder = StateGraph(State)
        builder.add_node("intake", lambda state: {})
        builder.add_edge(START, "intake")
        for route in router.routes:
            builder.add_node(route, lambda state, route=route: {"handled_by": route})
            builder.add_edge(route, END)
        wiring(builder, router, after="intake")
        graph = builder.compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "comparison"}}
        paused = graph.invoke({"messages": ["Please check my order and payment."]}, config)
        assert paused["__interrupt__"][0].value["reason"] == "llm_abstained"
        result = graph.invoke(Command(resume="billing"), config)
        print(result["support_route"])


if __name__ == "__main__":
    main()
