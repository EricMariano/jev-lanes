"""Run with ``uv run python examples/router_offline.py``; no API key or network required.

Shows the three lanes and a human review resumed with a checkpointer. The classifier and
the fallback model are fakes; real providers implement the same two protocols.
"""

from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from jev_lanes import Classification, JevRouter, Lanes
from jev_lanes.testing import FakeFallback, FakeJevClassifier


class State(TypedDict, total=False):
    messages: list[str]
    support_route: dict[str, Any]  # the router's state_key
    handled_by: str


router = JevRouter(
    name="support",
    routes={"orders": "Order status questions", "billing": "Invoices and payments"},
    lanes=Lanes(auto=0.85, llm=0.60),  # illustrative thresholds, not calibrated defaults
    classifier=FakeJevClassifier(
        Classification("orders", 0.95),  # auto
        Classification("orders", 0.70),  # llm
        Classification("orders", 0.30),  # human
    ),
    fallback=FakeFallback("billing"),
)

builder = StateGraph(State)
builder.add_node("intake", lambda state: {})
builder.add_node("orders", lambda state: {"handled_by": "orders"})
builder.add_node("billing", lambda state: {"handled_by": "billing"})
builder.add_edge(START, "intake")
router.attach(builder, after="intake")
builder.add_edge("orders", END)
builder.add_edge("billing", END)
graph = builder.compile(checkpointer=InMemorySaver())

for thread_id in ("auto", "llm", "human"):
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke({"messages": ["where is my parcel?"]}, config)
    if "__interrupt__" in result:
        print(f"{thread_id}: paused for review ({result['__interrupt__'][0].value['reason']})")
        result = graph.invoke(Command(resume="billing"), config)
    print(f"{thread_id}: handled_by={result['handled_by']}")
