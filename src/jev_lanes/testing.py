"""Deterministic fakes for tests: no network, no credentials, no provider calls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from jev_lanes.protocols import Classification


@dataclass(frozen=True)
class Call:
    """One recorded call: the payload received and a snapshot of the routes."""

    payload: object
    routes: Mapping[str, str]


class FakeJevClassifier:
    """Classifier that returns scripted ``Classification`` objects in order.

    Pass an ``Exception`` to simulate a provider failure. ``calls`` records every call, so
    tests can prove when the gate classified and when it did not.
    """

    def __init__(self, *results: Classification | Exception) -> None:
        self._results = list(results)
        self.calls: list[Call] = []

    def classify(self, payload: object, routes: Mapping[str, str]) -> Classification:
        self.calls.append(Call(payload, dict(routes)))
        if not self._results:
            raise RuntimeError("FakeJevClassifier has no scripted result left")
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeChatModel(BaseChatModel):
    """Chat model that replies with scripted messages in order.

    Items are ``AIMessage`` objects, plain strings (turned into an ``AIMessage``), or an
    ``Exception`` to raise. ``bind_tools`` returns the model itself. ``received`` records the
    messages of every call.
    """

    script: list[Any] = Field(default_factory=list)
    received: list[list[BaseMessage]] = Field(default_factory=list)

    def __init__(self, *script: AIMessage | str | Exception) -> None:
        super().__init__(script=list(script))  # type: ignore[call-arg]

    @property
    def _llm_type(self) -> str:
        return "jev-lanes-fake"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> FakeChatModel:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received.append(list(messages))
        if not self.script:
            raise RuntimeError("FakeChatModel has no scripted reply left")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        message = AIMessage(item) if isinstance(item, str) else item
        return ChatResult(generations=[ChatGeneration(message=message)])


def tool_call_message(name: str, args: Mapping[str, Any] | None = None, *, id: str) -> AIMessage:
    """An ``AIMessage`` proposing one tool call, for scripting ``FakeChatModel``."""
    return AIMessage("", tool_calls=[{"name": name, "args": dict(args or {}), "id": id}])
