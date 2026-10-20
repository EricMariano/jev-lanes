"""Smoke tests against the real services; see conftest.py for how to run them.

Needs TYPESAFE_API_KEY and a fallback provider. The fallback model defaults to
``openai:gpt-5-nano``, the cheapest OpenAI text model on the pricing page on 2026-10-20,
when OPENAI_API_KEY is set; set JEV_LIVE_FALLBACK_MODEL to use another
``init_chat_model`` string with that provider's key. No temperature is passed because
reasoning models such as gpt-5-nano reject ``temperature=0``. The cases are deliberately
unambiguous: these tests check the wire format end to end, not decision quality.
"""

import os
from typing import Any, TypedDict

import pytest
from langgraph.graph import END, START, StateGraph

from jev_lanes import Classification, JevRouter, Lanes, RouteTrace
from jev_lanes.adapters import JevClassifier, LangChainFallback

pytestmark = pytest.mark.live

DEFAULT_MODEL = "openai:gpt-5-nano"

ROUTES = {
    "orders": "Where is my order, delivery and tracking questions.",
    "billing": "Invoices, charges, refunds and payment problems.",
    "other": "Anything that fits none of the other routes.",
}
BILLING_CASE = ["I was charged twice for the same order, please refund the duplicate charge."]


def fallback_model() -> str:
    model = os.environ.get("JEV_LIVE_FALLBACK_MODEL")
    if model:
        return model
    if os.environ.get("OPENAI_API_KEY"):
        return DEFAULT_MODEL
    pytest.skip("set JEV_LIVE_FALLBACK_MODEL (and that provider's key) or OPENAI_API_KEY")


@pytest.fixture
def classifier() -> JevClassifier:
    if not os.environ.get("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY is not set")
    return JevClassifier()


@pytest.fixture
def fallback() -> LangChainFallback:
    return LangChainFallback(fallback_model())


def test_typesafe_classifies_a_clear_case(classifier):
    result = classifier.classify(BILLING_CASE, ROUTES)
    print(f"\nTypeSafe -> {result}")
    assert result.route == "billing"
    assert 0.0 <= result.confidence <= 1.0


def test_chat_model_names_a_route_for_a_clear_case(fallback):
    answer = fallback.decide(BILLING_CASE, ROUTES)
    print(f"\nfallback -> {answer!r}")
    assert answer == "billing"


def test_chat_model_abstains_or_names_a_route_for_gibberish(fallback):
    answer = fallback.decide(["asdf qwer zxcv 1234"], ROUTES)
    print(f"\nfallback on gibberish -> {answer!r}")
    assert answer is None or answer in ROUTES


class State(TypedDict, total=False):
    messages: list[str]
    support_route: dict[str, Any]
    handled_by: str


class CappedConfidence:
    """Real TypeSafe answer with confidence capped, to force the fallback lane."""

    def __init__(self, inner: JevClassifier, cap: float) -> None:
        self.inner, self.cap = inner, cap

    def classify(self, payload, routes):
        result = self.inner.classify(payload, routes)
        return Classification(result.route, min(result.confidence, self.cap))


def test_router_end_to_end_through_the_fallback_lane(classifier, fallback):
    # TypeSafe is fully confident on a clear case, which would stay in the auto lane.
    router = JevRouter(
        name="support",
        routes=ROUTES,
        lanes=Lanes(auto=0.85, llm=0.60),
        classifier=CappedConfidence(classifier, cap=0.7),
        fallback=fallback,
    )
    builder = StateGraph(State)
    builder.add_node("intake", lambda state: {})
    for route in ROUTES:
        builder.add_node(route, lambda state, route=route: {"handled_by": route})
    builder.add_edge(START, "intake")
    router.attach(builder, after="intake")
    for route in ROUTES:
        builder.add_edge(route, END)
    result = builder.compile().invoke({"messages": BILLING_CASE})
    trace = RouteTrace.from_dict(result["support_route"])
    print(f"\ntrace -> {trace.to_dict()}")
    assert "__interrupt__" not in result
    assert trace.lane == "llm"
    assert [e.evaluator for e in trace.evaluations] == ["jev", "llm"]
    assert result["handled_by"] == trace.final_route == "billing"
