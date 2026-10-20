import json

import pytest

from jev_lanes import Evaluation, RouteTrace


def jev(route="orders", confidence=0.9):
    return Evaluation("jev", route, confidence=confidence)


def llm(route, reason="low_confidence"):
    return Evaluation("llm", route, reason=reason)


def human(route, reason="low_confidence"):
    return Evaluation("human", route, reason=reason)


class TestEvaluation:
    def test_jev_requires_confidence_in_unit_interval(self):
        with pytest.raises(ValueError):
            Evaluation("jev", "orders")
        with pytest.raises(ValueError):
            Evaluation("jev", "orders", confidence=1.1)
        with pytest.raises(TypeError):
            Evaluation("jev", "orders", confidence=True)

    def test_only_jev_records_confidence_and_only_jev_has_no_reason(self):
        with pytest.raises(ValueError):
            Evaluation("llm", "orders", confidence=0.5, reason="low_confidence")
        with pytest.raises(ValueError):
            Evaluation("llm", "orders")
        with pytest.raises(ValueError):
            Evaluation("jev", "orders", confidence=0.9, reason="low_confidence")

    def test_only_llm_may_abstain(self):
        assert llm(None).route is None
        with pytest.raises(ValueError):
            human(None)
        with pytest.raises(ValueError):
            Evaluation("jev", None, confidence=0.9)

    def test_rejects_unknown_evaluator_reason_and_bad_route(self):
        with pytest.raises(ValueError):
            Evaluation("robot", "orders", reason="low_confidence")
        with pytest.raises(ValueError):
            llm("orders", reason="because")
        with pytest.raises(ValueError):
            jev(route="")
        with pytest.raises(TypeError):
            jev(route=3)


class TestRouteTrace:
    def test_auto_lane_decision(self):
        trace = RouteTrace("auto", [jev()], final_route="orders")
        assert trace.final_route == "orders"
        assert isinstance(trace.evaluations, tuple)

    def test_each_lane_may_be_persisted_before_escalation(self):
        assert RouteTrace("llm", [jev(confidence=0.7)]).final_route is None
        assert RouteTrace("human", [jev(confidence=0.2)]).final_route is None
        assert RouteTrace("llm", [jev(confidence=0.7), llm(None)]).final_route is None

    def test_llm_lane_accepts_llm_route(self):
        trace = RouteTrace("llm", [jev(confidence=0.7), llm("billing")], final_route="billing")
        assert trace.final_route == "billing"

    def test_llm_abstention_and_invalid_route_escalate_to_human(self):
        abstained = RouteTrace(
            "llm",
            [jev(confidence=0.7), llm(None), human("billing", "llm_abstained")],
            final_route="billing",
        )
        invalid = RouteTrace(
            "llm",
            [jev(confidence=0.7), llm("nope"), human("billing", "llm_invalid_route")],
            final_route="billing",
        )
        assert abstained.final_route == invalid.final_route == "billing"

    def test_human_lane_skips_llm(self):
        trace = RouteTrace("human", [jev(confidence=0.2), human("billing")], final_route="billing")
        assert trace.final_route == "billing"

    @pytest.mark.parametrize(
        ("lane", "evaluations"),
        [
            ("auto", [jev(), llm("orders")]),
            ("human", [jev(confidence=0.2), llm("orders")]),
            ("llm", [jev(confidence=0.7), human("orders")]),
            ("llm", [llm("orders")]),
            ("llm", []),
            ("auto", [jev(), jev()]),
        ],
    )
    def test_rejects_evaluator_sequences_the_lane_cannot_produce(self, lane, evaluations):
        with pytest.raises(ValueError):
            RouteTrace(lane, evaluations)

    def test_rejects_unknown_lane(self):
        with pytest.raises(ValueError):
            RouteTrace("fast", [jev()])

    def test_rejects_reasons_inconsistent_with_the_previous_evaluation(self):
        with pytest.raises(ValueError):
            RouteTrace("llm", [jev(confidence=0.7), llm(None), human("a", "low_confidence")])
        with pytest.raises(ValueError):
            RouteTrace("llm", [jev(confidence=0.7), llm("a"), human("b", "llm_abstained")])
        with pytest.raises(ValueError):
            RouteTrace("llm", [jev(confidence=0.7), llm(None), human("b", "llm_invalid_route")])

    def test_final_route_must_match_an_accepted_evaluation(self):
        with pytest.raises(ValueError):
            RouteTrace("auto", [jev()], final_route="billing")
        with pytest.raises(ValueError):
            RouteTrace("llm", [jev(confidence=0.7)], final_route="orders")
        with pytest.raises(ValueError):
            RouteTrace("llm", [jev(confidence=0.7), llm(None)], final_route="orders")
        with pytest.raises(ValueError):
            RouteTrace("auto", [jev()], final_route="")

    def test_json_round_trip(self):
        trace = RouteTrace(
            "llm",
            [jev(confidence=0.7), llm(None), human("billing", "llm_abstained")],
            final_route="billing",
        )
        data = json.loads(json.dumps(trace.to_dict()))
        assert RouteTrace.from_dict(data) == trace

    def test_from_dict_rejects_unknown_keys_and_invalid_data(self):
        data = RouteTrace("auto", [jev()], final_route="orders").to_dict()
        with pytest.raises(ValueError):
            RouteTrace.from_dict({**data, "text": "customer message"})
        data["evaluations"][0]["text"] = "customer message"
        with pytest.raises(ValueError):
            RouteTrace.from_dict(data)
        with pytest.raises(ValueError):
            RouteTrace.from_dict({"lane": "auto", "evaluations": [], "final_route": None})

    def test_serialized_form_holds_no_case_text(self):
        data = RouteTrace("auto", [jev()], final_route="orders").to_dict()
        assert set(data) == {"lane", "evaluations", "final_route"}
        assert set(data["evaluations"][0]) == {"evaluator", "route", "confidence", "reason"}
