from typing import Any, TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import ValidationError

from jev_lanes import Classification, JevRouter, Lanes, RouteTrace
from jev_lanes.router import INVALID_ROUTE
from jev_lanes.testing import FakeFallback, FakeJevClassifier

ROUTES = {"orders": "Order status questions", "billing": "Invoices and payments"}
LANES = Lanes(auto=0.85, llm=0.60)


class State(TypedDict, total=False):
    messages: list[str]
    support_route: dict[str, Any]
    handled_by: str


def make_router(classifier, fallback=None, **kwargs):
    return JevRouter(
        name="support",
        routes=ROUTES,
        lanes=LANES,
        classifier=classifier,
        fallback=fallback or FakeFallback(),
        **kwargs,
    )


def build(router, *, checkpointer=None):
    builder = StateGraph(State)
    builder.add_node("intake", lambda state: {})
    builder.add_node("orders", lambda state: {"handled_by": "orders"})
    builder.add_node("billing", lambda state: {"handled_by": "billing"})
    builder.add_edge(START, "intake")
    router.attach(builder, after="intake")
    builder.add_edge("orders", END)
    builder.add_edge("billing", END)
    return builder.compile(checkpointer=checkpointer)


CASE = {"messages": ["where is my parcel?"]}
CONFIG = {"configurable": {"thread_id": "t1"}}


def trace_of(result) -> RouteTrace:
    return RouteTrace.from_dict(result["support_route"])


class TestAutoLane:
    def test_routes_directly_without_fallback_or_checkpointer(self):
        classifier = FakeJevClassifier(Classification("orders", 0.95))
        fallback = FakeFallback()
        result = build(make_router(classifier, fallback)).invoke(CASE)
        assert result["handled_by"] == "orders"
        trace = trace_of(result)
        assert (trace.lane, trace.final_route) == ("auto", "orders")
        assert [e.evaluator for e in trace.evaluations] == ["jev"]
        assert fallback.calls == []

    def test_sends_messages_and_route_descriptions_to_the_classifier(self):
        classifier = FakeJevClassifier(Classification("billing", 0.9))
        build(make_router(classifier)).invoke(CASE)
        assert classifier.calls[0].payload == ["where is my parcel?"]
        assert classifier.calls[0].routes == ROUTES

    def test_extract_controls_what_leaves_the_state(self):
        classifier = FakeJevClassifier(Classification("orders", 0.9))
        router = make_router(classifier, extract=lambda state: state["messages"][-1].upper())
        build(router).invoke(CASE)
        assert classifier.calls[0].payload == "WHERE IS MY PARCEL?"


class TestLlmLane:
    def test_accepts_a_valid_fallback_route(self):
        classifier = FakeJevClassifier(Classification("orders", 0.7))
        fallback = FakeFallback("billing")
        result = build(make_router(classifier, fallback)).invoke(CASE)
        assert result["handled_by"] == "billing"
        trace = trace_of(result)
        assert [e.evaluator for e in trace.evaluations] == ["jev", "llm"]
        assert (trace.lane, trace.final_route) == ("llm", "billing")
        assert fallback.calls[0].payload == ["where is my parcel?"]

    @pytest.mark.parametrize(
        ("answer", "reason"), [(None, "llm_abstained"), ("refunds", "llm_invalid_route")]
    )
    def test_abstention_or_unknown_route_goes_to_human_review(self, answer, reason):
        classifier = FakeJevClassifier(Classification("orders", 0.7))
        graph = build(make_router(classifier, FakeFallback(answer)), checkpointer=InMemorySaver())
        paused = graph.invoke(CASE, CONFIG)
        review = paused["__interrupt__"][0].value
        assert review["reason"] == reason
        assert review["router"] == "support"
        assert review["routes"] == ROUTES
        assert "handled_by" not in paused
        assert trace_of(paused).final_route is None
        resumed = graph.invoke(Command(resume="billing"), CONFIG)
        assert resumed["handled_by"] == "billing"
        trace = trace_of(resumed)
        assert [e.evaluator for e in trace.evaluations] == ["jev", "llm", "human"]
        assert trace.evaluations[-1].reason == reason

    def test_unknown_fallback_answer_is_not_stored_in_the_trace(self):
        secret = "my card number is 4111 1111 1111 1111"
        classifier = FakeJevClassifier(Classification("orders", 0.7))
        graph = build(make_router(classifier, FakeFallback(secret)), checkpointer=InMemorySaver())
        paused = graph.invoke(CASE, CONFIG)
        llm_step = trace_of(paused).evaluations[-1]
        assert llm_step.route == INVALID_ROUTE
        assert secret not in repr(paused["__interrupt__"][0].value)
        assert secret not in repr(paused["support_route"])


class TestHumanLane:
    def test_skips_the_fallback_and_pauses_for_review(self):
        classifier = FakeJevClassifier(Classification("orders", 0.2))
        fallback = FakeFallback()
        graph = build(make_router(classifier, fallback), checkpointer=InMemorySaver())
        paused = graph.invoke(CASE, CONFIG)
        review = paused["__interrupt__"][0].value
        assert review["reason"] == "low_confidence"
        assert [s["evaluator"] for s in review["suggestions"]] == ["jev"]
        assert fallback.calls == []
        assert trace_of(graph.invoke(Command(resume="orders"), CONFIG)).final_route == "orders"

    def test_resuming_does_not_classify_again(self):
        classifier = FakeJevClassifier(Classification("orders", 0.2))
        graph = build(make_router(classifier), checkpointer=InMemorySaver())
        graph.invoke(CASE, CONFIG)
        assert len(classifier.calls) == 1
        graph.invoke(Command(resume="billing"), CONFIG)
        assert len(classifier.calls) == 1

    def test_unknown_human_route_is_rejected_and_can_be_answered_again(self):
        classifier = FakeJevClassifier(Classification("orders", 0.2))
        graph = build(make_router(classifier), checkpointer=InMemorySaver())
        graph.invoke(CASE, CONFIG)
        with pytest.raises(ValidationError):
            graph.invoke(Command(resume="refunds"), CONFIG)
        assert graph.get_state(CONFIG).next == ("support_human",)
        resumed = graph.invoke(Command(resume="billing"), CONFIG)
        assert resumed["handled_by"] == "billing"
        assert len(classifier.calls) == 1

    def test_interrupt_value_does_not_contain_the_case_text(self):
        classifier = FakeJevClassifier(Classification("orders", 0.2))
        graph = build(make_router(classifier), checkpointer=InMemorySaver())
        review = graph.invoke(CASE, CONFIG)["__interrupt__"][0].value
        assert "parcel" not in repr(review)


class TestFailures:
    def test_classifier_failure_propagates(self):
        graph = build(make_router(FakeJevClassifier(TimeoutError("down"))))
        with pytest.raises(TimeoutError):
            graph.invoke(CASE)

    def test_fallback_failure_propagates_instead_of_escalating(self):
        classifier = FakeJevClassifier(Classification("orders", 0.7))
        graph = build(make_router(classifier, FakeFallback(ConnectionError("down"))))
        with pytest.raises(ConnectionError):
            graph.invoke(CASE)

    def test_classifier_returning_an_unknown_route_is_an_error(self):
        graph = build(make_router(FakeJevClassifier(Classification("refunds", 0.9))))
        with pytest.raises(ValueError, match="unknown route"):
            graph.invoke(CASE)

    def test_missing_messages_without_extract_is_a_clear_error(self):
        graph = build(make_router(FakeJevClassifier(Classification("orders", 0.9))))
        with pytest.raises(ValueError, match="extract"):
            graph.invoke({})


class TestIsolationAndEpisodes:
    def test_each_invocation_starts_a_new_episode(self):
        classifier = FakeJevClassifier(
            Classification("orders", 0.9), Classification("billing", 0.9)
        )
        graph = build(make_router(classifier), checkpointer=InMemorySaver())
        first = graph.invoke(CASE, CONFIG)
        second = graph.invoke(CASE, CONFIG)
        assert (first["handled_by"], second["handled_by"]) == ("orders", "billing")
        assert len(trace_of(second).evaluations) == 1

    def test_two_routers_use_separate_state_keys(self):
        class Two(TypedDict, total=False):
            messages: list[str]
            first_route: dict[str, Any]
            second_route: dict[str, Any]

        def router(name, route):
            return JevRouter(
                name=name,
                routes={"a": "A", "b": "B"},
                lanes=LANES,
                classifier=FakeJevClassifier(Classification(route, 0.9)),
                fallback=FakeFallback(),
            )

        builder = StateGraph(Two)
        builder.add_node("a", lambda state: {})
        builder.add_node("b", lambda state: {})
        first, second = router("first", "a"), router("second", "b")
        builder.add_edge(START, "a")
        first.attach(builder, after="a", targets={"a": "b", "b": END})
        second.attach(builder, after="b", targets={"a": END, "b": END})
        result = builder.compile().invoke(CASE)
        assert RouteTrace.from_dict(result["first_route"]).final_route == "a"
        assert RouteTrace.from_dict(result["second_route"]).final_route == "b"


class TestConfiguration:
    def test_rejects_invalid_arguments(self):
        classifier = FakeJevClassifier()
        good = {
            "routes": ROUTES,
            "lanes": LANES,
            "classifier": classifier,
            "fallback": FakeFallback(),
        }
        for name in ("", "1st", "has space", "a:b"):
            with pytest.raises(ValueError):
                JevRouter(name=name, **good)
        with pytest.raises(ValueError):
            JevRouter(name="x", **{**good, "routes": {}})
        with pytest.raises(TypeError):
            JevRouter(name="x", **{**good, "classifier": object()})
        with pytest.raises(TypeError):
            JevRouter(name="x", **{**good, "fallback": object()})
        with pytest.raises(TypeError):
            JevRouter(name="x", **{**good, "lanes": (0.8, 0.5)})

    def test_routes_are_copied_and_read_only(self):
        routes = dict(ROUTES)
        router = JevRouter(
            name="x",
            routes=routes,
            lanes=LANES,
            classifier=FakeJevClassifier(),
            fallback=FakeFallback(),
        )
        routes["extra"] = "later"
        assert "extra" not in router.routes
        with pytest.raises(TypeError):
            router.routes["extra"] = "nope"

    def test_attach_requires_targets_for_exactly_the_routes(self):
        router = make_router(FakeJevClassifier())
        builder = StateGraph(State)
        builder.add_node("intake", lambda state: {})
        with pytest.raises(ValueError):
            router.attach(builder, after="intake", targets={"orders": "orders"})
        with pytest.raises(ValueError):
            router.attach(
                builder,
                after="intake",
                targets={"orders": "o", "billing": "b", "refunds": "r"},
            )

    def test_attaching_two_routers_with_the_same_name_fails_clearly(self):
        builder = StateGraph(State)
        builder.add_node("intake", lambda state: {})
        make_router(FakeJevClassifier()).attach(builder, after="intake")
        with pytest.raises(ValueError, match="needs its own name"):
            make_router(FakeJevClassifier()).attach(builder, after="intake")
