# Changelog

## Unreleased

Rewrite around confidence-gated tools. Breaking: nothing from `0.1.0rc1` was ever published.

- `GatedTool`: a LangChain tool plus the intents it serves and its minimum Jev confidence.
- `GatedAgent`: a LangGraph agent that classifies only when the model proposes a tool call,
  runs all proposed calls or none, asks the customer a clarifying question through
  `interrupt()` and refuses with a fixed message after `max_clarifications`.
- `GateTrace` / `Check`: serializable record of each check (tool, intent, confidence,
  requirement, outcome) and the questions spent. No message text or tool arguments.
- `FakeChatModel` and `tool_call_message` for offline tests; `FakeJevClassifier` stays.
- Customer-service demo run in CI, and a bring-your-own-keys chat.
- Banking77 gate evaluation (`clarify.py`, `gate_report.py`) with recorded answers and
  report. Asking recovers some blocked customers but is only slightly better than lowering
  the threshold, with a simulated customer that favours asking.
- Removed: `Lanes`, `JevRouter`, `FallbackModel`, `LangChainFallback`, the human-review lane,
  the notebook and the old examples. The first design's evaluation stays as history: its
  LLM fallback did not improve Jev's decisions.
- `benchmarks/banking77/run.py` and `benchmarks/smoke_battery.py` are archived; they need
  commit `8d07291`.

Limitations: synchronous execution only; confidence requirements are not calibrated; the
evaluation uses a simulated customer and does not include the agent's language model. The
TypeSafe integration is an alpha dependency. The unused `notebook` dependency group is kept
until `uv.lock` is regenerated.

## 0.1.0rc1 — 2026-10-23

First local release candidate of the three-lane router (confidence bands, LangChain fallback
and resumable human review). Superseded before publication; see the history above.
