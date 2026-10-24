"""``GatedAgent``: a tool-calling LangGraph agent whose autonomy follows classifier confidence.

The model proposes tool calls. Before any runs, the gate classifies the conversation and
checks every proposed call against its tool's requirement (``GatedTool``). If all calls
pass they run. If one does not, none run: the agent asks the customer one question (the
graph pauses on ``interrupt()`` until it is resumed with the answer), then proposes again.
After ``max_clarifications`` rounds without enough confidence the turn ends with a fixed
refusal and no side effect. Classification runs only when the model proposes a tool call,
so small talk costs nothing.

Everything the gate stores in the graph state lives under ``gate`` as
``GateTrace.to_dict()``. Every invocation starts a new turn with a fresh trace.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Any, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, interrupt

from jev_lanes.gate import GatedTool
from jev_lanes.protocols import Classifier
from jev_lanes.trace import GateTrace

START_NODE = "start"
AGENT_NODE = "agent"
GATE_NODE = "gate"
TOOLS_NODE = "tools"
ASK_NODE = "ask"
AWAIT_NODE = "await_reply"
REFUSE_NODE = "refuse"

DEFAULT_REFUSAL = (
    "I couldn't confirm what you need, so I haven't done anything. "
    "Please describe the request in more detail or contact support."
)
DEFAULT_QUESTION = "Could you tell me a bit more about what you need?"

_ASK_PROMPT = (
    "The action you just proposed was not run because the customer's request is not clear "
    "enough to authorize it. Write one short question for the customer that would settle "
    "what they want. Do not call tools, do not apologize at length, and do not mention "
    "confidence or internal checks."
)
_DENIED = "Not run: the customer's request is not clear enough to authorize this action."
_HELD = "Not run: another action in the same step needs clarification first."


class GatedState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    gate: dict[str, Any]


def default_extract(state: Mapping[str, Any]) -> object:
    """Send the conversation text (customer and assistant turns) to the classifier.

    Tool calls and tool results are left out: they add noise and may carry data that need
    not leave your environment. Pass ``extract=`` to the agent to choose differently.
    """
    messages = state.get("messages", [])
    text = [m for m in messages if isinstance(m, (HumanMessage, AIMessage)) and m.text]
    if not text:
        raise ValueError("the conversation has no text to classify; pass extract=...")
    return text


@dataclass(frozen=True, eq=False)
class GatedAgent:
    """Tool-calling agent whose tools are gated by classifier confidence.

    ``intents`` maps each intent name to its description (the classifier's criteria). Every
    tool's intents must be among them. ``model`` must support ``bind_tools``. ``extract``
    receives the graph state and returns the payload sent to the classifier. ``refusal``
    is the fixed message that ends a turn after ``max_clarifications`` unanswered rounds;
    ``question`` is used when the model does not write a usable clarifying question.
    """

    model: BaseChatModel
    tools: Sequence[GatedTool]
    intents: Mapping[str, str]
    classifier: Classifier
    max_clarifications: int = 2
    instructions: str | None = None
    refusal: str = DEFAULT_REFUSAL
    question: str = DEFAULT_QUESTION
    extract: Callable[[Mapping[str, Any]], object] = default_extract

    def __post_init__(self) -> None:
        if not isinstance(self.model, BaseChatModel):
            raise TypeError("model must be a LangChain BaseChatModel")
        tools = tuple(self.tools)
        if not tools or not all(isinstance(item, GatedTool) for item in tools):
            raise TypeError("tools must be a non-empty sequence of GatedTool")
        names = [item.name for item in tools]
        if len(set(names)) != len(names):
            raise ValueError("tool names must be unique")
        if not self.intents:
            raise ValueError("intents must not be empty")
        if not all(isinstance(k, str) and k for k in self.intents):
            raise ValueError("intent names must be non-empty strings")
        if not all(isinstance(v, str) for v in self.intents.values()):
            raise TypeError("intent descriptions must be strings")
        for item in tools:
            unknown = sorted(item.intents - set(self.intents))
            if unknown:
                raise ValueError(f"tool {item.name!r} serves unknown intents {unknown}")
        if not isinstance(self.classifier, Classifier):
            raise TypeError("classifier must provide classify(payload, routes)")
        if isinstance(self.max_clarifications, bool) or not isinstance(
            self.max_clarifications, int
        ):
            raise TypeError("max_clarifications must be an int")
        if self.max_clarifications < 0:
            raise ValueError("max_clarifications must not be negative")
        if not callable(self.extract):
            raise TypeError("extract must be callable")
        object.__setattr__(self, "tools", tools)
        object.__setattr__(self, "intents", MappingProxyType(dict(self.intents)))

    # -- nodes -------------------------------------------------------------------------

    def start(self, state: GatedState) -> dict[str, Any]:
        """Begin a new turn with an empty trace."""
        return {"gate": GateTrace().to_dict()}

    def call_model(self, state: GatedState) -> dict[str, Any]:
        """Let the model answer or propose tool calls. Nothing is executed here."""
        reply = self._bound().invoke(self._prompt(state))
        return {"messages": [reply]}

    def authorize(self, state: GatedState) -> Command[str]:
        """Classify and check every proposed call; run all of them or none.

        A provider failure raises; it is never converted into a low confidence. When any
        call is not allowed, every call in the step gets an error result (the provider
        needs one per call) and the turn moves to clarification or refusal.
        """
        trace = self._load(state)
        calls = self._proposed_calls(state)
        registry = {item.name: item for item in self.tools}
        known = [call for call in calls if call["name"] in registry]
        if not known:
            # Only unknown tool names: ToolNode answers each with an error, nothing runs.
            return Command(goto=TOOLS_NODE)
        classification = self.classifier.classify(self.extract(state), self.intents)
        if classification.route not in self.intents:
            raise ValueError(f"classifier returned unknown intent {classification.route!r}")
        checks = tuple(registry[call["name"]].authorize(classification) for call in known)
        trace = GateTrace((*trace.checks, *checks), trace.clarifications, trace.refused)
        denied = {c.tool for c in checks if not c.allowed}
        if not denied:
            return Command(update={"gate": trace.to_dict()}, goto=TOOLS_NODE)
        blocked = [
            ToolMessage(
                _DENIED if call["name"] in denied else _HELD,
                tool_call_id=call["id"],
                name=call["name"],
                status="error",
            )
            for call in calls
        ]
        if trace.clarifications < self.max_clarifications:
            goto = ASK_NODE
        else:
            trace = GateTrace(trace.checks, trace.clarifications, refused=True)
            goto = REFUSE_NODE
        return Command(update={"messages": blocked, "gate": trace.to_dict()}, goto=goto)

    def ask(self, state: GatedState) -> dict[str, Any]:
        """Write the clarifying question. Kept apart from the pause so resuming never asks again."""
        reply = self._bound().invoke([*self._prompt(state), SystemMessage(_ASK_PROMPT)])
        usable = not reply.tool_calls and reply.text.strip()
        return {"messages": [AIMessage(reply.text.strip() if usable else self.question)]}

    def await_reply(self, state: GatedState) -> dict[str, Any]:
        """Pause for the customer's answer; ``Command(resume="<text>")`` resumes.

        The surfaced value holds the question and the round number, nothing else. A resume
        value that is not text is rejected by LangGraph and can be sent again.
        """
        trace = self._load(state)
        question = state["messages"][-1].text
        payload = {"question": question, "round": trace.clarifications + 1}
        answer = interrupt(payload, response_schema=str)
        updated = GateTrace(trace.checks, trace.clarifications + 1, trace.refused)
        return {"messages": [HumanMessage(answer)], "gate": updated.to_dict()}

    def refuse(self, state: GatedState) -> dict[str, Any]:
        """End the turn with the fixed refusal. Nothing with a side effect has run."""
        return {"messages": [AIMessage(self.refusal)]}

    # -- graph -------------------------------------------------------------------------

    def build(self) -> StateGraph[GatedState, Any, GatedState, GatedState]:
        """Return the uncompiled graph, for callers who add nodes or compile themselves."""
        builder = StateGraph(GatedState)
        builder.add_node(START_NODE, self.start)
        builder.add_node(AGENT_NODE, self.call_model)
        builder.add_node(
            GATE_NODE, self.authorize, destinations=(TOOLS_NODE, ASK_NODE, REFUSE_NODE)
        )
        builder.add_node(TOOLS_NODE, ToolNode([item.tool for item in self.tools]))
        builder.add_node(ASK_NODE, self.ask)
        builder.add_node(AWAIT_NODE, self.await_reply)
        builder.add_node(REFUSE_NODE, self.refuse)
        builder.add_edge(START, START_NODE)
        builder.add_edge(START_NODE, AGENT_NODE)
        builder.add_conditional_edges(AGENT_NODE, _after_model, [GATE_NODE, END])
        builder.add_edge(TOOLS_NODE, AGENT_NODE)
        builder.add_edge(ASK_NODE, AWAIT_NODE)
        builder.add_edge(AWAIT_NODE, AGENT_NODE)
        builder.add_edge(REFUSE_NODE, END)
        return builder

    def compile(
        self, checkpointer: BaseCheckpointSaver[Any] | None = None
    ) -> CompiledStateGraph[GatedState, Any, GatedState, GatedState]:
        """Compile the graph. Clarification needs a checkpointer and a stable ``thread_id``."""
        return self.build().compile(checkpointer=checkpointer)

    # -- helpers -----------------------------------------------------------------------

    def _bound(self) -> Any:
        return self.model.bind_tools([item.tool for item in self.tools])

    def _prompt(self, state: GatedState) -> list[BaseMessage]:
        head: list[BaseMessage] = [SystemMessage(self.instructions)] if self.instructions else []
        return [*head, *state["messages"]]

    def _load(self, state: GatedState) -> GateTrace:
        try:
            data = state["gate"]
        except KeyError:
            raise ValueError("the graph state has no 'gate' key") from None
        return GateTrace.from_dict(data)

    @staticmethod
    def _proposed_calls(state: GatedState) -> list[Any]:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            raise ValueError("the gate runs only after the model proposes tool calls")
        return list(last.tool_calls)


def _after_model(state: GatedState) -> str:
    last = state["messages"][-1]
    return GATE_NODE if isinstance(last, AIMessage) and last.tool_calls else END
