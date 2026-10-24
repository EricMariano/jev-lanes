"""Per-tool confidence requirements, independent of providers and graph execution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from langchain_core.tools import BaseTool

from jev_lanes._validate import validate_name, validate_unit_interval
from jev_lanes.protocols import Classification
from jev_lanes.trace import Check, CheckOutcome


@dataclass(frozen=True, init=False)
class GatedTool:
    """A LangChain tool plus what the classifier must say before the agent may run it.

    The tool runs only when the classified intent is one of ``intents`` and its confidence
    is at least ``min_confidence`` (equality allows). Use a high ``min_confidence`` for
    actions that are hard to undo. Confidence is a distribution statistic, not an accuracy
    guarantee: select the values with domain-specific evaluation, no defaults are supplied.
    """

    tool: BaseTool
    intents: frozenset[str]
    min_confidence: float

    def __init__(self, tool: BaseTool, intents: Iterable[str], min_confidence: float) -> None:
        if not isinstance(tool, BaseTool):
            raise TypeError("tool must be a LangChain BaseTool")
        if isinstance(intents, str):
            raise TypeError("intents must be an iterable of intent names, not a string")
        names = frozenset(intents)
        if not names:
            raise ValueError("intents must not be empty")
        for item in names:
            validate_name(item, name="intent")
        validate_unit_interval(min_confidence, name="min_confidence")
        object.__setattr__(self, "tool", tool)
        object.__setattr__(self, "intents", names)
        object.__setattr__(self, "min_confidence", min_confidence)

    @property
    def name(self) -> str:
        return self.tool.name

    def authorize(self, classification: Classification) -> Check:
        """Check this tool against a classification. Pure: nothing is executed."""
        outcome: CheckOutcome
        if classification.route not in self.intents:
            outcome = "intent_mismatch"
        elif classification.confidence < self.min_confidence:
            outcome = "low_confidence"
        else:
            outcome = "allowed"
        return Check(
            tool=self.name,
            intent=classification.route,
            confidence=classification.confidence,
            required=self.min_confidence,
            outcome=outcome,
        )
