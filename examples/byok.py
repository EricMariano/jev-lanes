"""Real providers, bring your own keys. Not run in CI: it calls external services.

    export TYPESAFE_API_KEY=...      # classifier (TypeSafe)
    export OPENAI_API_KEY=...        # fallback provider; install its package, e.g. langchain-openai
    uv run python examples/byok.py

The case text is sent to TypeSafe and, for medium-confidence cases, to the fallback
provider. Use ``extract=`` on ``JevRouter`` to restrict or redact what is sent.
Thresholds are illustrative; calibrate them on your own labeled data.
"""

from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from jev_lanes import JevRouter, Lanes
from jev_lanes.adapters import JevClassifier, LangChainFallback


class State(TypedDict, total=False):
    messages: list[str]
    support_route: dict[str, Any]
    handled_by: str


router = JevRouter(
    name="support",
    routes={
        "orders": "Where is my order, delivery and tracking questions.",
        "billing": "Invoices, charges, refunds and payment problems.",
        "other": "Anything that fits none of the other routes.",
    },
    lanes=Lanes(auto=0.85, llm=0.60),
    classifier=JevClassifier(),
    fallback=LangChainFallback("openai:gpt-4.1-mini", temperature=0),
)

builder = StateGraph(State)
builder.add_node("intake", lambda state: {})
for route in router.routes:
    builder.add_node(route, lambda state, route=route: {"handled_by": route})
builder.add_edge(START, "intake")
router.attach(builder, after="intake")
for route in router.routes:
    builder.add_edge(route, END)
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "demo"}}
result = graph.invoke({"messages": ["I was charged twice for my last order"]}, config)
if "__interrupt__" in result:
    review = result["__interrupt__"][0].value
    print("Human review needed:", review["reason"], review["suggestions"])
    result = graph.invoke(Command(resume="billing"), config)
print("handled_by:", result["handled_by"])
print("trace:", result["support_route"])
