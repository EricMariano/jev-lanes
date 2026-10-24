from typing import Any

import pytest
from langchain_typesafe import ChoiceAnswer, ClassifierResponse, NoulAnswer

from jev_lanes import Classifier
from jev_lanes.adapters import JevClassifier

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
        assert question.instructions == "What does the customer want?"

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
