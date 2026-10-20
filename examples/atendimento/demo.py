"""Customer-service demo: ``uv run python examples/atendimento/demo.py``.

All provider responses and human decisions are scripted. No keys or network needed.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import ValidationError

from jev_lanes import Classification, JevRouter, Lanes, RouteTrace
from jev_lanes.protocols import Classifier, FallbackModel
from jev_lanes.testing import FakeFallback, FakeJevClassifier

ROUTES = {
    "orders": "Order status, tracking, delivery and cancellation.",
    "billing": "Invoices, duplicate charges, payments and refunds.",
    "account": "Login, password and profile changes.",
}


class SupportState(TypedDict, total=False):
    messages: list[str]
    support_route: dict[str, Any]
    handled_by: str
    reply: str


def build_graph(classifier: Classifier, fallback: FallbackModel) -> Any:
    """Create a support graph with separate handlers and in-memory checkpoints."""
    router = JevRouter(
        name="support",
        routes=ROUTES,
        lanes=Lanes(auto=0.85, llm=0.60),  # examples, not calibrated thresholds
        classifier=classifier,
        fallback=fallback,
    )
    replies = {
        "orders": "The orders team will check your delivery.",
        "billing": "The billing team will review the charge.",
        "account": "The account team will help restore access.",
    }
    builder = StateGraph(SupportState)
    builder.add_node("intake", lambda state: {})
    builder.add_edge(START, "intake")
    for route, reply in replies.items():
        builder.add_node(
            route,
            lambda state, route=route, reply=reply: {"handled_by": route, "reply": reply},
        )
        builder.add_edge(route, END)
    router.attach(builder, after="intake")
    return builder.compile(checkpointer=InMemorySaver())


def main() -> None:
    classifier = FakeJevClassifier(
        Classification("orders", 0.95),
        Classification("orders", 0.70),
        Classification("account", 0.30),
        Classification("orders", 0.70),
    )
    fallback = FakeFallback("billing", None)
    graph = build_graph(classifier, fallback)
    cases = (
        ("auto", "Where is my parcel?", None),
        ("llm", "I was charged for a cancelled order.", None),
        ("human", "I cannot log in and need to change my payment card.", "account"),
        ("abstention", "The order and the payment look wrong.", "billing"),
    )
    for thread_id, message, human_route in cases:
        config = {"configurable": {"thread_id": thread_id}}
        calls_before = len(classifier.calls)
        result = graph.invoke({"messages": [message]}, config)
        if "__interrupt__" in result:
            review = result["__interrupt__"][0].value
            print(f"{thread_id}: paused ({review['reason']}); choose from {list(review['routes'])}")
            assert "handled_by" not in result  # no handler ran before approval
            assert graph.get_state(config).next == ("support_human",)
            # The first reviewer response is deliberately invalid; the same review survives.
            try:
                graph.invoke(Command(resume="unknown_team"), config)
            except ValidationError:
                print(f"{thread_id}: invalid review rejected; waiting for a valid route")
            else:
                raise AssertionError("invalid review should have been rejected")
            result = graph.invoke(Command(resume=human_route), config)
        assert len(classifier.calls) == calls_before + 1  # resume never classifies again
        trace = RouteTrace.from_dict(result["support_route"])
        print(f"{thread_id}: {result['reply']}")
        print(f"  lane={trace.lane}; evaluators={[e.evaluator for e in trace.evaluations]}")
    assert len(fallback.calls) == 2
    print("All four cases completed; each classified once.")


if __name__ == "__main__":
    main()
