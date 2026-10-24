"""Offline demo: three conversations through a GatedAgent, with scripted fakes.

No keys, no network. The scripted classifier plays the part of Jev, so what this shows is
the wiring (when the agent acts, asks or refuses), not how well Jev classifies.

    python examples/atendimento/demo.py
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from support import INSTRUCTIONS, INTENTS, BackOffice, build_tools

from jev_lanes import Classification, GatedAgent, GateTrace
from jev_lanes.testing import FakeChatModel, FakeJevClassifier, tool_call_message


def converse(
    title: str,
    model: FakeChatModel,
    classifier: FakeJevClassifier,
    office: BackOffice,
    first_message: str,
    answers: list[str],
) -> GateTrace:
    agent = GatedAgent(
        model=model,
        tools=build_tools(office),
        intents=INTENTS,
        classifier=classifier,
        instructions=INSTRUCTIONS,
        max_clarifications=2,
    )
    graph = agent.compile(InMemorySaver())
    config: dict[str, Any] = {"configurable": {"thread_id": title}}

    result = graph.invoke({"messages": [HumanMessage(first_message)]}, config)
    while "__interrupt__" in result:
        result = graph.invoke(Command(resume=answers.pop(0)), config)

    print(f"\n=== {title} ===")
    for message in graph.get_state(config).values["messages"]:
        if isinstance(message, HumanMessage):
            print(f"customer: {message.text}")
        elif isinstance(message, ToolMessage):
            print(f"  [{message.status}: {message.text}]")
        elif message.tool_calls:
            call = message.tool_calls[0]
            print(f"  [model proposes {call['name']}({call['args']})]")
        else:
            print(f"agent: {message.text}")
    trace = GateTrace.from_dict(graph.get_state(config).values["gate"])
    for check in trace.checks:
        print(
            f"  gate: {check.tool} <- {check.intent} {check.confidence:.2f} "
            f"(needs {check.required:.2f}) {check.outcome}"
        )
    return trace


def main() -> None:
    # 1. Clear request: the read-only tool needs 0.50 and gets 0.93, so it just runs.
    office = BackOffice()
    trace = converse(
        "clear request",
        FakeChatModel(
            tool_call_message("order_status", {"order_id": "A100"}, id="c1"),
            "Order A100 has shipped.",
        ),
        FakeJevClassifier(Classification("orders", 0.93)),
        office,
        "Where is my order A100?",
        [],
    )
    assert trace.clarifications == 0 and not trace.refused

    # 2. Vague request for a refund: 0.62 is below the 0.90 a refund needs, so the agent
    #    asks. After the answer the classifier is confident and the refund runs.
    office = BackOffice()
    trace = converse(
        "vague, then clear",
        FakeChatModel(
            tool_call_message("refund", {"order_id": "A100"}, id="c1"),
            "Which order is this about, and what went wrong?",
            tool_call_message("refund", {"order_id": "A100"}, id="c2"),
            "Done: order A100 is refunded.",
        ),
        FakeJevClassifier(Classification("billing", 0.62), Classification("billing", 0.96)),
        office,
        "I want my money back.",
        ["Order A100 arrived broken, please refund it."],
    )
    assert office.refunds == ["A100"] and trace.clarifications == 1

    # 3. The customer never makes it clear: after two questions the agent refuses, and the
    #    irreversible tool never ran.
    office = BackOffice()
    trace = converse(
        "never clear",
        FakeChatModel(
            tool_call_message("refund", {"order_id": "A100"}, id="c1"),
            "Could you tell me which order you mean?",
            tool_call_message("refund", {"order_id": "A100"}, id="c2"),
            "What would you like us to do about it?",
            tool_call_message("refund", {"order_id": "A100"}, id="c3"),
        ),
        FakeJevClassifier(
            Classification("billing", 0.41),
            Classification("billing", 0.48),
            Classification("other", 0.55),
        ),
        office,
        "It's about the thing.",
        ["The thing from before.", "You know."],
    )
    assert office.refunds == [] and trace.refused and trace.clarifications == 2


if __name__ == "__main__":
    main()
