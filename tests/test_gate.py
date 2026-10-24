import pytest
from langchain_core.tools import tool

from jev_lanes import Classification, GatedTool


@tool
def refund(order_id: str) -> str:
    """Refund an order."""
    return f"refunded {order_id}"


def gated(intents=("billing",), min_confidence=0.9):
    return GatedTool(refund, intents, min_confidence)


class TestAuthorize:
    def test_allows_the_right_intent_at_or_above_the_requirement(self):
        assert gated().authorize(Classification("billing", 0.95)).allowed
        assert gated().authorize(Classification("billing", 0.9)).allowed

    def test_low_confidence_blocks(self):
        check = gated().authorize(Classification("billing", 0.89))
        assert check.outcome == "low_confidence"
        assert (check.tool, check.intent, check.required) == ("refund", "billing", 0.9)

    def test_wrong_intent_blocks_even_when_very_confident(self):
        check = gated().authorize(Classification("orders", 0.99))
        assert check.outcome == "intent_mismatch"

    def test_wrong_intent_wins_over_low_confidence(self):
        assert gated().authorize(Classification("orders", 0.1)).outcome == "intent_mismatch"

    def test_a_tool_may_serve_several_intents(self):
        item = gated(intents=("billing", "account"))
        assert item.authorize(Classification("account", 0.95)).allowed

    def test_a_zero_requirement_still_needs_the_intent(self):
        item = gated(min_confidence=0.0)
        assert item.authorize(Classification("billing", 0.0)).allowed
        assert not item.authorize(Classification("orders", 1.0)).allowed


class TestConstruction:
    def test_exposes_the_tool_name(self):
        assert gated().name == "refund"

    def test_intents_are_frozen(self):
        assert gated(intents=["billing", "billing"]).intents == frozenset({"billing"})

    def test_rejects_invalid_arguments(self):
        with pytest.raises(TypeError, match="BaseTool"):
            GatedTool(lambda: None, ["billing"], 0.5)
        with pytest.raises(TypeError, match="not a string"):
            gated(intents="billing")
        with pytest.raises(ValueError, match="empty"):
            gated(intents=[])
        with pytest.raises(ValueError):
            gated(intents=[""])
        with pytest.raises(ValueError):
            gated(min_confidence=1.5)
        with pytest.raises(TypeError):
            gated(min_confidence=True)
