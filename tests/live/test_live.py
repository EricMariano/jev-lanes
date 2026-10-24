"""Smoke test against the real classifier; see conftest.py for how to run it.

Needs TYPESAFE_API_KEY. The case is deliberately unambiguous: this checks the wire format
end to end, not decision quality.
"""

import os

import pytest

from jev_lanes.adapters import JevClassifier

pytestmark = pytest.mark.live

INTENTS = {
    "orders": "Where is my order, delivery and tracking questions.",
    "billing": "Invoices, charges, refunds and payment problems.",
    "other": "Anything that fits none of the other intents.",
}
BILLING_CASE = ["I was charged twice for the same order, please refund the duplicate charge."]


@pytest.fixture
def classifier() -> JevClassifier:
    if not os.environ.get("TYPESAFE_API_KEY"):
        pytest.skip("TYPESAFE_API_KEY is not set")
    return JevClassifier()


def test_typesafe_classifies_a_clear_case(classifier):
    result = classifier.classify(BILLING_CASE, INTENTS)
    print(f"\nTypeSafe -> {result}")
    assert result.route == "billing"
    assert 0.0 <= result.confidence <= 1.0
