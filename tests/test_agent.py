import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError

from jev_lanes import Classification, GatedAgent, GatedTool, GateTrace
from jev_lanes.agent import DEFAULT_QUESTION, DEFAULT_REFUSAL, default_extract
from jev_lanes.testing import FakeChatModel, FakeJevClassifier, tool_call_message

INTENTS = {
    "orders": "Where is my order, delivery and tracking questions.",
    "billing": "Invoices, charges, refunds and payment problems.",
}
RUNS: list[str] = []


@tool
def order_status(order_id: str) -> str:
    """Look up an order."""
    RUNS.append(f"status:{order_id}")
    return f"{order_id} shipped"


@tool
def refund(order_id: str) -> str:
    """Refund an order."""
    RUNS.append(f"refund:{order_id}")
    return f"{order_id} refunded"


@pytest.fixture(autouse=True)
def clear_runs():
    RUNS.clear()


def make(model, classifier, **options):
    tools = [
        GatedTool(order_status, ["orders"], 0.5),
        GatedTool(refund, ["billing"], 0.9),
    ]
    agent = GatedAgent(model=model, tools=tools, intents=INTENTS, classifier=classifier, **options)
    return agent, agent.compile(InMemorySaver())


def config(thread="t1"):
    return {"configurable": {"thread_id": thread}}


def say(text):
    return {"messages": [HumanMessage(text)]}


def trace_of(graph, cfg):
    return GateTrace.from_dict(graph.get_state(cfg).values["gate"])


def pending(result):
    return result["__interrupt__"][0].value


class TestConfidentRequest:
    def test_runs_the_tool_and_answers(self):
        model = FakeChatModel(tool_call_message("refund", {"order_id": "A1"}, id="c1"), "Done.")
        classifier = FakeJevClassifier(Classification("billing", 0.95))
        _, graph = make(model, classifier)
        result = graph.invoke(say("refund order A1"), config())
        assert RUNS == ["refund:A1"]
        assert result["messages"][-1].text == "Done."
        assert "__interrupt__" not in result
        assert len(classifier.calls) == 1
        assert [c.outcome for c in trace_of(graph, config()).checks] == ["allowed"]

    def test_small_talk_never_calls_the_classifier(self):
        classifier = FakeJevClassifier()
        _, graph = make(FakeChatModel("Hello! How can I help?"), classifier)
        result = graph.invoke(say("hi"), config())
        assert result["messages"][-1].text == "Hello! How can I help?"
        assert classifier.calls == []
        assert trace_of(graph, config()) == GateTrace()

    def test_requirement_is_per_tool(self):
        # 0.7 is enough to look an order up (0.5) but not to refund (0.9).
        model = FakeChatModel(tool_call_message("order_status", {"order_id": "A1"}, id="c1"), "ok")
        _, graph = make(model, FakeJevClassifier(Classification("orders", 0.7)))
        graph.invoke(say("where is A1"), config())
        assert RUNS == ["status:A1"]


class TestClarification:
    def test_asks_the_customer_then_runs_once_confident(self):
        model = FakeChatModel(
            tool_call_message("refund", {"order_id": "A1"}, id="c1"),
            "Which order do you want refunded, and why?",
            tool_call_message("refund", {"order_id": "A1"}, id="c2"),
            "Refund issued.",
        )
        classifier = FakeJevClassifier(
            Classification("billing", 0.6), Classification("billing", 0.97)
        )
        _, graph = make(model, classifier)
        cfg = config()

        paused = graph.invoke(say("do something with my order"), cfg)
        assert pending(paused) == {
            "question": "Which order do you want refunded, and why?",
            "round": 1,
        }
        assert RUNS == []
        assert len(classifier.calls) == 1  # pausing does not classify again

        done = graph.invoke(Command(resume="Refund A1, it arrived broken"), cfg)
        assert RUNS == ["refund:A1"]
        assert done["messages"][-1].text == "Refund issued."
        assert len(classifier.calls) == 2
        trace = trace_of(graph, cfg)
        assert trace.clarifications == 1
        assert [c.outcome for c in trace.checks] == ["low_confidence", "allowed"]

    def test_blocked_calls_get_error_results_the_model_can_follow(self):
        model = FakeChatModel(
            tool_call_message("refund", {"order_id": "A1"}, id="c1"), "Which order?"
        )
        _, graph = make(model, FakeJevClassifier(Classification("billing", 0.6)))
        graph.invoke(say("refund"), config())
        history = graph.get_state(config()).values["messages"]
        assert [type(m) for m in history] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
        blocked = history[2]
        assert (blocked.tool_call_id, blocked.status) == ("c1", "error")
        assert "0.6" not in blocked.text and "0.9" not in blocked.text

    def test_the_question_prompt_asks_for_no_tools(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"), "Which order?")
        _, graph = make(model, FakeJevClassifier(Classification("billing", 0.6)))
        graph.invoke(say("refund"), config())
        asked = model.received[1][-1]
        assert "Do not call tools" in asked.text

    @pytest.mark.parametrize("reply", [tool_call_message("refund", id="c9"), "   ", ""])
    def test_an_unusable_question_falls_back_to_the_default(self, reply):
        model = FakeChatModel(tool_call_message("refund", id="c1"), reply)
        _, graph = make(model, FakeJevClassifier(Classification("billing", 0.6)))
        paused = graph.invoke(say("refund"), config())
        assert pending(paused)["question"] == DEFAULT_QUESTION
        assert RUNS == []

    def test_a_custom_default_question(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"), "")
        _, graph = make(
            model, FakeJevClassifier(Classification("billing", 0.6)), question="More detail?"
        )
        assert pending(graph.invoke(say("refund"), config()))["question"] == "More detail?"

    def test_a_non_text_answer_is_rejected_and_can_be_sent_again(self):
        call = {"order_id": "A1"}
        model = FakeChatModel(
            tool_call_message("refund", call, id="c1"),
            "Which order?",
            tool_call_message("refund", call, id="c2"),
            "Done.",
        )
        classifier = FakeJevClassifier(
            Classification("billing", 0.6), Classification("billing", 0.97)
        )
        _, graph = make(model, classifier)
        graph.invoke(say("refund"), config())
        with pytest.raises(ValidationError):
            graph.invoke(Command(resume=42), config())
        assert RUNS == []
        graph.invoke(Command(resume="A1"), config())
        assert RUNS == ["refund:A1"]


class TestRefusal:
    def test_refuses_after_the_allowed_clarifications(self):
        model = FakeChatModel(
            tool_call_message("refund", id="c1"),
            "Which order?",
            tool_call_message("refund", id="c2"),
        )
        classifier = FakeJevClassifier(
            Classification("billing", 0.6), Classification("billing", 0.7)
        )
        _, graph = make(model, classifier, max_clarifications=1)
        graph.invoke(say("refund"), config())
        done = graph.invoke(Command(resume="the red one"), config())
        assert RUNS == []
        assert done["messages"][-1].text == DEFAULT_REFUSAL
        trace = trace_of(graph, config())
        assert trace.refused and trace.clarifications == 1

    def test_zero_clarifications_refuses_at_once_with_a_custom_message(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"))
        _, graph = make(
            model,
            FakeJevClassifier(Classification("billing", 0.6)),
            max_clarifications=0,
            refusal="Please call us.",
        )
        result = graph.invoke(say("refund"), config())
        assert "__interrupt__" not in result
        assert result["messages"][-1].text == "Please call us."
        assert RUNS == []

    def test_every_proposed_call_is_answered_so_history_stays_valid(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"))
        _, graph = make(
            model, FakeJevClassifier(Classification("billing", 0.6)), max_clarifications=0
        )
        graph.invoke(say("refund"), config())
        history = graph.get_state(config()).values["messages"]
        assert [type(m) for m in history] == [HumanMessage, AIMessage, ToolMessage, AIMessage]


class TestBlocking:
    def test_a_confident_intent_that_does_not_fit_the_tool_blocks_it(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"), "Which order?")
        _, graph = make(model, FakeJevClassifier(Classification("orders", 0.99)))
        graph.invoke(say("where is my parcel"), config())
        assert RUNS == []
        assert [c.outcome for c in trace_of(graph, config()).checks] == ["intent_mismatch"]

    def test_one_blocked_call_holds_the_whole_step(self):
        both = AIMessage(
            "",
            tool_calls=[
                {"name": "order_status", "args": {"order_id": "A1"}, "id": "c1"},
                {"name": "refund", "args": {"order_id": "A1"}, "id": "c2"},
            ],
        )
        model = FakeChatModel(both, "Which order?")
        # "orders" at 0.8 would allow order_status, but refund serves "billing".
        _, graph = make(model, FakeJevClassifier(Classification("orders", 0.8)))
        graph.invoke(say("status and refund"), config())
        assert RUNS == []
        history = graph.get_state(config()).values["messages"]
        results = {m.tool_call_id: m.text for m in history if isinstance(m, ToolMessage)}
        assert set(results) == {"c1", "c2"}
        assert "another action" in results["c1"]
        assert "not clear enough" in results["c2"]

    def test_unknown_tool_names_reach_the_tool_node_without_classifying(self):
        model = FakeChatModel(tool_call_message("delete_everything", id="c1"), "Sorry.")
        classifier = FakeJevClassifier()
        _, graph = make(model, classifier)
        result = graph.invoke(say("do it"), config())
        assert classifier.calls == []
        assert RUNS == []
        errors = [m for m in result["messages"] if isinstance(m, ToolMessage)]
        assert errors and errors[0].status == "error"

    def test_provider_failure_raises_and_nothing_runs(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"))
        _, graph = make(model, FakeJevClassifier(TimeoutError("typesafe down")))
        with pytest.raises(TimeoutError):
            graph.invoke(say("refund"), config())
        assert RUNS == []

    def test_unknown_intent_from_the_classifier_is_an_error(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"))
        _, graph = make(model, FakeJevClassifier(Classification("sales", 0.99)))
        with pytest.raises(ValueError, match="unknown intent"):
            graph.invoke(say("refund"), config())
        assert RUNS == []


class TestTurns:
    def test_each_invocation_starts_a_fresh_trace(self):
        model = FakeChatModel(
            tool_call_message("refund", id="c1"),
            "Which order?",
            tool_call_message("refund", id="c2"),
            "Done.",
            "Anything else?",
        )
        classifier = FakeJevClassifier(
            Classification("billing", 0.6), Classification("billing", 0.97)
        )
        _, graph = make(model, classifier)
        graph.invoke(say("refund"), config())
        graph.invoke(Command(resume="A1"), config())
        assert trace_of(graph, config()).clarifications == 1
        graph.invoke(say("thanks"), config())
        assert trace_of(graph, config()) == GateTrace()

    def test_the_trace_never_holds_case_text(self):
        model = FakeChatModel(tool_call_message("refund", {"order_id": "SECRET-42"}, id="c1"), "?")
        _, graph = make(model, FakeJevClassifier(Classification("billing", 0.6)))
        graph.invoke(say("my card 4111 is broken"), config())
        dumped = str(graph.get_state(config()).values["gate"])
        assert "4111" not in dumped and "SECRET-42" not in dumped


class TestExtract:
    def test_default_extract_sends_only_conversation_text(self):
        model = FakeChatModel(tool_call_message("refund", {"order_id": "A1"}, id="c1"), "Done.")
        classifier = FakeJevClassifier(Classification("billing", 0.95))
        _, graph = make(model, classifier)
        graph.invoke(say("refund A1"), config())
        payload = classifier.calls[0].payload
        assert [type(m) for m in payload] == [HumanMessage]

    def test_default_extract_needs_some_text(self):
        with pytest.raises(ValueError, match="no text"):
            default_extract({"messages": [tool_call_message("refund", id="c1")]})

    def test_a_custom_extract_chooses_the_payload(self):
        model = FakeChatModel(tool_call_message("refund", id="c1"), "Done.")
        classifier = FakeJevClassifier(Classification("billing", 0.95))
        _, graph = make(model, classifier, extract=lambda state: "REDACTED")
        graph.invoke(say("my card is 4111"), config())
        assert classifier.calls[0].payload == "REDACTED"


class TestConstruction:
    def build(self, **overrides):
        options = {
            "model": FakeChatModel(),
            "tools": [GatedTool(refund, ["billing"], 0.9)],
            "intents": INTENTS,
            "classifier": FakeJevClassifier(),
        }
        return GatedAgent(**{**options, **overrides})

    def test_instructions_lead_the_prompt(self):
        model = FakeChatModel("Hi")
        agent = self.build(model=model, instructions="You are a support agent.")
        agent.compile().invoke(say("hi"))
        assert model.received[0][0].text == "You are a support agent."

    def test_intents_are_a_snapshot(self):
        intents = dict(INTENTS)
        agent = self.build(intents=intents)
        intents["extra"] = "later"
        assert "extra" not in agent.intents

    def test_rejects_invalid_arguments(self):
        with pytest.raises(TypeError, match="BaseChatModel"):
            self.build(model="gpt")
        with pytest.raises(TypeError, match="GatedTool"):
            self.build(tools=[refund])
        with pytest.raises(TypeError, match="GatedTool"):
            self.build(tools=[])
        with pytest.raises(ValueError, match="unique"):
            self.build(tools=[GatedTool(refund, ["billing"], 0.9)] * 2)
        with pytest.raises(ValueError, match="unknown intents"):
            self.build(tools=[GatedTool(refund, ["sales"], 0.9)])
        with pytest.raises(ValueError, match="empty"):
            self.build(intents={})
        with pytest.raises(TypeError, match="classify"):
            self.build(classifier=object())
        with pytest.raises(ValueError, match="negative"):
            self.build(max_clarifications=-1)
        with pytest.raises(TypeError):
            self.build(max_clarifications=True)
        with pytest.raises(TypeError, match="callable"):
            self.build(extract=None)
