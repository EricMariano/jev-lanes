import pytest

from jev_lanes import Classification, Classifier, FallbackModel
from jev_lanes.testing import FakeFallback, FakeJevClassifier

ROUTES = {"orders": "Order status questions", "billing": "Invoices and payments"}


class TestClassification:
    def test_accepts_valid_values(self):
        result = Classification("orders", 0.0)
        assert (result.route, result.confidence) == ("orders", 0.0)

    @pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf")])
    def test_rejects_invalid_confidence(self, confidence):
        with pytest.raises(ValueError):
            Classification("orders", confidence)

    def test_rejects_invalid_types_and_empty_route(self):
        with pytest.raises(TypeError):
            Classification("orders", True)
        with pytest.raises(TypeError):
            Classification(None, 0.5)
        with pytest.raises(ValueError):
            Classification("", 0.5)


class TestFakeJevClassifier:
    def test_satisfies_the_classifier_protocol(self):
        assert isinstance(FakeJevClassifier(), Classifier)

    def test_plays_results_in_order_and_records_calls(self):
        first, second = Classification("orders", 0.9), Classification("billing", 0.4)
        fake = FakeJevClassifier(first, second)
        assert fake.classify("where is my parcel", ROUTES) == first
        assert fake.classify("refund", ROUTES) == second
        assert [call.payload for call in fake.calls] == ["where is my parcel", "refund"]
        assert fake.calls[0].routes == ROUTES

    def test_records_a_snapshot_of_routes(self):
        routes = dict(ROUTES)
        fake = FakeJevClassifier(Classification("orders", 0.9))
        fake.classify("x", routes)
        routes["extra"] = "later change"
        assert "extra" not in fake.calls[0].routes

    def test_raises_scripted_exception_as_a_provider_failure(self):
        fake = FakeJevClassifier(TimeoutError("provider timeout"))
        with pytest.raises(TimeoutError):
            fake.classify("x", ROUTES)
        assert len(fake.calls) == 1

    def test_fails_loudly_when_the_script_is_exhausted(self):
        fake = FakeJevClassifier()
        with pytest.raises(RuntimeError, match="no scripted result"):
            fake.classify("x", ROUTES)
        assert len(fake.calls) == 1


class TestFakeFallback:
    def test_satisfies_the_fallback_protocol(self):
        assert isinstance(FakeFallback(), FallbackModel)

    def test_returns_route_or_abstains_in_order(self):
        fake = FakeFallback("billing", None)
        assert fake.decide("x", ROUTES) == "billing"
        assert fake.decide("y", ROUTES) is None
        assert [call.payload for call in fake.calls] == ["x", "y"]

    def test_raises_scripted_exception_and_fails_when_exhausted(self):
        fake = FakeFallback(ConnectionError("down"))
        with pytest.raises(ConnectionError):
            fake.decide("x", ROUTES)
        with pytest.raises(RuntimeError, match="no scripted result"):
            fake.decide("x", ROUTES)
