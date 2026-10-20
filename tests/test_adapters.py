from typing import Any, TypedDict

import pytest
from langchain_core.language_models import BaseChatModel, FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_typesafe import ChoiceAnswer, ClassifierResponse, NoulAnswer
from langgraph.graph import END, START, StateGraph

from jev_lanes import Classifier, FallbackModel, JevRouter, Lanes, RouteTrace
from jev_lanes.adapters import JevClassifier, LangChainFallback, parse_route, render_payload

ROUTES = {"orders": "Order status questions", "billing": "Invoices and payments"}


class FakeTypeSafe:
    """Stands in for ``TypeSafeClassifier``; records requests, replies with a scripted answer."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.requests: list[dict[str, Any]] = []

    def invoke(self, request: dict[str, Any]) -> ClassifierResponse:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ClassifierResponse(model="jev-test", answers=answer)


def choice(label: str, confidence: float) -> dict[str, Any]:
    probabilities = {name: 0.0 for name in ROUTES}
    probabilities[label] = 1.0
    return {
        "route": ChoiceAnswer(
            type="choice", choice=label, probabilities=probabilities, confidence=confidence
        )
    }


class RecordingChat(FakeListChatModel):
    """Fake chat model that keeps the messages it was invoked with."""

    seen: list[Any] = []

    def invoke(self, input, config=None, **kwargs):  # noqa: A002
        self.seen.append(input)
        return super().invoke(input, config, **kwargs)


def chat(*replies: str) -> RecordingChat:
    return RecordingChat(responses=list(replies), seen=[])


class TestJevClassifier:
    def test_sends_state_and_routes_as_a_choice_question(self):
        client = FakeTypeSafe(choice("billing", 0.8))
        result = JevClassifier(client=client).classify(["hello"], ROUTES)
        assert (result.route, result.confidence) == ("billing", 0.8)
        request = client.requests[0]
        assert request["state"] == ["hello"]
        question = request["questions"]["route"]
        assert question.type == "choice"
        assert question.criteria == ROUTES
        assert question.instructions == "Which route should handle this case?"

    def test_custom_instructions(self):
        client = FakeTypeSafe(choice("orders", 0.5))
        JevClassifier(instructions="Which team?", client=client).classify("x", ROUTES)
        assert client.requests[0]["questions"]["route"].instructions == "Which team?"

    def test_missing_or_wrong_type_of_answer_is_an_error(self):
        wrong_type = {"route": NoulAnswer(type="noul", noul=0.5)}
        for answers in ({}, wrong_type):
            with pytest.raises(ValueError, match="no answer"):
                JevClassifier(client=FakeTypeSafe(answers)).classify("x", ROUTES)

    def test_provider_failures_propagate(self):
        client = FakeTypeSafe(TimeoutError("timeout"))
        with pytest.raises(TimeoutError):
            JevClassifier(client=client).classify("x", ROUTES)

    def test_satisfies_the_classifier_protocol(self):
        assert isinstance(JevClassifier(client=FakeTypeSafe()), Classifier)

    def test_missing_api_key_fails_at_construction(self, monkeypatch):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
            JevClassifier()

    def test_builds_a_typesafe_client_from_the_environment_without_network(self, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
        assert isinstance(JevClassifier(), Classifier)
        assert isinstance(JevClassifier(timeout=5), Classifier)

    def test_client_and_options_are_mutually_exclusive(self):
        with pytest.raises(TypeError):
            JevClassifier(client=FakeTypeSafe(), timeout=5)


class TestLangChainFallback:
    def test_returns_the_route_named_by_the_model(self):
        model = chat("billing")
        fallback = LangChainFallback(model)
        assert fallback.decide("refund please", ROUTES) == "billing"
        system, human = model.seen[0]
        assert "orders: Order status questions" in system.content
        assert "billing: Invoices and payments" in system.content
        assert "ABSTAIN" in system.content
        assert human.content == "<case>\nrefund please\n</case>"

    def test_satisfies_the_fallback_protocol(self):
        assert isinstance(LangChainFallback(chat()), FallbackModel)

    def test_abstains(self):
        assert LangChainFallback(chat("ABSTAIN")).decide("x", ROUTES) is None
        assert LangChainFallback(chat("  abstain.\n")).decide("x", ROUTES) is None

    def test_renders_message_payloads(self):
        model = chat("orders")
        LangChainFallback(model).decide(
            [HumanMessage("where is it?"), AIMessage("checking")], ROUTES
        )
        assert model.seen[0][1].content == "<case>\nhuman: where is it?\nai: checking\n</case>"

    def test_model_failure_propagates(self):
        class Broken(BaseChatModel):
            @property
            def _llm_type(self) -> str:
                return "broken"

            def _generate(self, *args, **kwargs):
                raise ConnectionError("provider down")

        with pytest.raises(ConnectionError):
            LangChainFallback(Broken()).decide("x", ROUTES)

    def test_abstain_cannot_be_a_route_name(self):
        with pytest.raises(ValueError, match="reserved"):
            LangChainFallback(chat("x")).decide("x", {"abstain": "nope"})

    def test_string_models_go_through_init_chat_model(self, monkeypatch):
        import langchain.chat_models as chat_models

        calls = []
        model = chat("orders")

        def fake_init(name, **options):
            calls.append((name, options))
            return model

        monkeypatch.setattr(chat_models, "init_chat_model", fake_init)
        fallback = LangChainFallback("openai:some-model", temperature=0)
        assert calls == [("openai:some-model", {"temperature": 0})]
        assert fallback.decide("x", ROUTES) == "orders"

    def test_rejects_invalid_models_and_options(self):
        with pytest.raises(TypeError):
            LangChainFallback(object())
        with pytest.raises(TypeError):
            LangChainFallback(chat(), temperature=0)


class TestParseAndRender:
    @pytest.mark.parametrize(
        ("reply", "expected"),
        [
            ("billing", "billing"),
            ("  Billing\n", "billing"),
            ('"billing".', "billing"),
            ("`orders`", "orders"),
            ("billing\nbecause it is about money", "billing"),
            ("ABSTAIN", None),
            ("Abstain.", None),
            ("refunds", "refunds"),
            ("", "<empty reply>"),
        ],
    )
    def test_parse_route(self, reply, expected):
        assert parse_route(reply, ROUTES) == expected

    def test_unmatched_replies_are_truncated(self):
        assert len(parse_route("x" * 500, ROUTES)) == 100

    def test_ambiguous_case_insensitive_match_is_not_guessed(self):
        routes = {"Sales": "a", "sales": "b"}
        assert parse_route("SALES", routes) == "SALES"
        assert parse_route("sales", routes) == "sales"

    def test_render_payload(self):
        assert render_payload("text") == "text"
        assert render_payload({"a": "é"}) == '{"a": "é"}'
        assert render_payload(["a", "b"]) == "a\nb"
        assert render_payload(3) == "3"


class State(TypedDict, total=False):
    messages: list[str]
    support_route: dict[str, Any]
    handled_by: str


class TestWithRouter:
    def build(self, client, model):
        router = JevRouter(
            name="support",
            routes=ROUTES,
            lanes=Lanes(auto=0.85, llm=0.60),
            classifier=JevClassifier(client=client),
            fallback=LangChainFallback(model),
        )
        builder = StateGraph(State)
        builder.add_node("intake", lambda state: {})
        builder.add_node("orders", lambda state: {"handled_by": "orders"})
        builder.add_node("billing", lambda state: {"handled_by": "billing"})
        builder.add_edge(START, "intake")
        router.attach(builder, after="intake")
        builder.add_edge("orders", END)
        builder.add_edge("billing", END)
        return builder.compile()

    def test_medium_confidence_is_decided_by_the_chat_model(self):
        client, model = FakeTypeSafe(choice("orders", 0.7)), chat("billing")
        result = self.build(client, model).invoke({"messages": ["I was charged twice"]})
        assert result["handled_by"] == "billing"
        trace = RouteTrace.from_dict(result["support_route"])
        assert [e.evaluator for e in trace.evaluations] == ["jev", "llm"]
        assert client.requests[0]["state"] == ["I was charged twice"]
        assert "I was charged twice" in model.seen[0][1].content

    def test_high_confidence_never_calls_the_chat_model(self):
        client, model = FakeTypeSafe(choice("orders", 0.95)), chat()
        result = self.build(client, model).invoke({"messages": ["where is my parcel?"]})
        assert result["handled_by"] == "orders"
        assert model.seen == []
