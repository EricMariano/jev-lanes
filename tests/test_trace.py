import json

import pytest

from jev_lanes import Check, GateTrace


def check(outcome="allowed", confidence=0.9, required=0.8, tool="refund", intent="billing"):
    return Check(tool, intent, confidence, required, outcome)


class TestCheck:
    def test_accepts_each_outcome(self):
        assert check("allowed").allowed
        assert not check("low_confidence", confidence=0.5).allowed
        assert not check("intent_mismatch").allowed

    def test_equality_with_the_requirement_is_allowed(self):
        assert check("allowed", confidence=0.8, required=0.8).allowed

    def test_outcome_must_agree_with_the_numbers(self):
        with pytest.raises(ValueError, match="allowed"):
            check("allowed", confidence=0.5)
        with pytest.raises(ValueError, match="low_confidence"):
            check("low_confidence", confidence=0.9)

    def test_intent_mismatch_may_have_any_confidence(self):
        check("intent_mismatch", confidence=0.99)
        check("intent_mismatch", confidence=0.1)

    @pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
    def test_rejects_invalid_numbers(self, value):
        with pytest.raises(ValueError):
            check(confidence=value)
        with pytest.raises(ValueError):
            check(required=value)

    def test_rejects_invalid_types_and_names(self):
        with pytest.raises(TypeError):
            check(confidence=True)
        with pytest.raises(TypeError):
            check(tool=3)
        with pytest.raises(ValueError):
            check(intent="")
        with pytest.raises(ValueError, match="outcome"):
            check("maybe")

    def test_round_trips_through_json(self):
        item = check("low_confidence", confidence=0.5)
        assert Check.from_dict(json.loads(json.dumps(item.to_dict()))) == item

    def test_rejects_unknown_keys(self):
        with pytest.raises(ValueError, match="unknown check keys"):
            Check.from_dict({**check().to_dict(), "text": "leak"})


class TestGateTrace:
    def test_defaults_to_an_empty_turn(self):
        trace = GateTrace()
        assert (trace.checks, trace.clarifications, trace.refused) == ((), 0, False)

    def test_checks_become_a_tuple(self):
        assert isinstance(GateTrace([check()]).checks, tuple)

    def test_rejects_invalid_fields(self):
        with pytest.raises(TypeError):
            GateTrace(["not a check"])
        with pytest.raises(ValueError):
            GateTrace(clarifications=-1)
        with pytest.raises(TypeError):
            GateTrace(clarifications=True)
        with pytest.raises(TypeError):
            GateTrace(refused=1)

    def test_a_refused_turn_ends_with_a_check_that_was_not_allowed(self):
        with pytest.raises(ValueError, match="refused"):
            GateTrace(refused=True)
        with pytest.raises(ValueError, match="refused"):
            GateTrace((check("allowed"),), refused=True)
        GateTrace((check("low_confidence", confidence=0.5),), refused=True)

    def test_round_trips_through_json(self):
        trace = GateTrace(
            (check("low_confidence", confidence=0.5), check("allowed")), clarifications=1
        )
        assert GateTrace.from_dict(json.loads(json.dumps(trace.to_dict()))) == trace

    def test_rejects_unknown_keys_and_missing_fields(self):
        with pytest.raises(ValueError, match="unknown trace keys"):
            GateTrace.from_dict({**GateTrace().to_dict(), "messages": []})
        with pytest.raises(KeyError):
            GateTrace.from_dict({"checks": []})
