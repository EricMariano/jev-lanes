"""Default classifier for ``GatedAgent`` (bring your own key).

``JevClassifier`` calls TypeSafe through ``langchain-typesafe`` and reads
``TYPESAFE_API_KEY``. This package never stores or forwards keys. The conversation text you
send leaves your environment and goes to TypeSafe.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langchain_typesafe import Choice, TypeSafeClassifier

from jev_lanes.protocols import Classification

_QUESTION_ID = "route"


class JevClassifier:
    """``Classifier`` backed by a TypeSafe ``Choice`` whose criteria are the agent's intents.

    ``instructions`` is the question put to the model. Extra keyword arguments (``model``,
    ``api_key``, ``base_url``, ``timeout``) configure the ``TypeSafeClassifier`` created
    here; alternatively pass a ready ``client``. A missing key fails at construction.
    TypeSafe suggests an ``other`` route when the routes may not cover every input.
    """

    def __init__(
        self,
        *,
        instructions: str = "Which route should handle this case?",
        client: TypeSafeClassifier | None = None,
        **options: Any,
    ) -> None:
        if client is not None and options:
            raise TypeError("pass either client or TypeSafeClassifier options, not both")
        self._instructions = instructions
        self._client = client if client is not None else TypeSafeClassifier(**options)

    def classify(self, payload: object, routes: Mapping[str, str]) -> Classification:
        question = Choice(instructions=self._instructions, criteria=dict(routes))
        response = self._client.invoke(
            {"state": payload, "questions": {_QUESTION_ID: question}}  # type: ignore[typeddict-item]
        )
        answer = response.choices.get(_QUESTION_ID)
        if answer is None:
            raise ValueError("TypeSafe response has no answer for the routing question")
        return Classification(answer.choice, answer.confidence)
