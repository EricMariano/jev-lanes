"""Chat with a GatedAgent using real providers (bring your own keys).

Calls real services and may cost money; it is not run in CI. Needs TYPESAFE_API_KEY for Jev
and the key of the chat model's provider (``openai:gpt-5-nano`` by default, which needs
OPENAI_API_KEY and ``pip install langchain-openai``). Your conversation text is sent to both
providers. The minimum confidences in support.py are illustrative: measure them on your own
labelled data before relying on them.

    uv run --env-file .env python examples/atendimento/byok.py
"""

from __future__ import annotations

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from support import INSTRUCTIONS, INTENTS, BackOffice, build_tools

from jev_lanes import GatedAgent
from jev_lanes.adapters import JevClassifier


def main() -> None:
    office = BackOffice()
    agent = GatedAgent(
        model=init_chat_model(os.environ.get("JEV_CHAT_MODEL", "openai:gpt-5-nano")),
        tools=build_tools(office),
        intents=INTENTS,
        classifier=JevClassifier(),
        instructions=INSTRUCTIONS,
    )
    graph = agent.compile(InMemorySaver())
    config: dict[str, Any] = {"configurable": {"thread_id": "byok"}}

    print("Customer service (empty line to quit). Orders: A100 shipped, B200 packing.")
    while text := input("you: ").strip():
        result = graph.invoke({"messages": [HumanMessage(text)]}, config)
        while "__interrupt__" in result:
            print(f"agent: {result['__interrupt__'][0].value['question']}")
            result = graph.invoke(Command(resume=input("you: ")), config)
        print(f"agent: {result['messages'][-1].text}")
        print(f"  (refunds so far: {office.refunds})")


if __name__ == "__main__":
    main()
