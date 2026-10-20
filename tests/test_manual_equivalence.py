"""Compare observable behavior of manual wiring and attach(), including failures."""

import runpy
from pathlib import Path
from typing import Any, TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import ValidationError

from jev_lanes import Classification, JevRouter, Lanes
from jev_lanes.testing import FakeFallback, FakeJevClassifier

wire_manually = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "examples" / "manual_routing.py")
)["wire_manually"]


class State(TypedDict, total=False):
    messages: list[str]
    support_route: dict[str, Any]
    handled_by: str


def observe(manual, classification, fallback_answer, *, shared_target=False):
    classifier = FakeJevClassifier(classification, Classification("orders", 0.95))
    fallback = FakeFallback(fallback_answer)
    router = JevRouter(
        name="support",
        routes={"orders": "Delivery", "billing": "Payments"},
        lanes=Lanes(auto=0.85, llm=0.60),
        classifier=classifier,
        fallback=fallback,
    )
    targets = {"orders": "handler", "billing": "handler" if shared_target else END}
    builder = StateGraph(State)
    builder.add_node("intake", lambda state: {})
    builder.add_node("handler", lambda state: {"handled_by": "handler"})
    builder.add_edge(START, "intake")
    builder.add_edge("handler", END)
    if manual:
        wire_manually(builder, router, after="intake", targets=targets)
    else:
        router.attach(builder, after="intake", targets=targets)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "equivalence"}}
    observations = []
    try:
        result = graph.invoke({"messages": ["Please check my order."]}, config)
        if "__interrupt__" in result:
            observations.append(
                (
                    "paused",
                    result["support_route"],
                    result["__interrupt__"][0].value,
                    graph.get_state(config).next,
                    result.get("handled_by"),
                )
            )
            with pytest.raises(ValidationError):
                graph.invoke(Command(resume="invalid"), config)
            observations.append(("invalid_resume", graph.get_state(config).next))
            result = graph.invoke(Command(resume="billing"), config)
        observations.append(("done", result, graph.get_state(config).next))
        # A new episode must replace the trace rather than append to the previous one.
        next_result = graph.invoke({"messages": ["Another parcel."]}, config)
        observations.append(("next_episode", next_result))
    except (TimeoutError, ConnectionError, ValueError) as error:
        observations.append(("error", type(error).__name__, str(error)))
    return observations, classifier.calls, fallback.calls


@pytest.mark.parametrize("shared_target", [False, True])
@pytest.mark.parametrize(
    ("classification", "fallback"),
    [
        (Classification("orders", 0.95), None),
        (Classification("billing", 0.85), None),  # boundary routes straight to END
        (Classification("orders", 0.60), "billing"),  # boundary enters fallback
        (Classification("orders", 0.70), None),
        (Classification("orders", 0.70), "unknown"),
        (Classification("orders", 0.30), None),
        (Classification("unknown", 0.95), None),
        (TimeoutError("classifier unavailable"), None),
        (Classification("orders", 0.70), ConnectionError("fallback unavailable")),
    ],
)
def test_manual_and_attached_have_equivalent_behavior(classification, fallback, shared_target):
    args = (classification, fallback)
    assert observe(True, *args, shared_target=shared_target) == observe(
        False, *args, shared_target=shared_target
    )
