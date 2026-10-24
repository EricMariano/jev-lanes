# Changelog

## 0.1.0rc1 — 2026-10-23

First local release candidate; not yet published to PyPI.

- Explicit confidence bands with validated thresholds and serializable decision traces.
- Synchronous `JevRouter` with automatic routing, LangChain fallback and resumable human
  review. Invalid human routes are rejected; resuming does not repeat classification.
- Injectable classifier and fallback protocols, deterministic fakes, and BYOK TypeSafe
  and LangChain adapters. Provider failures propagate instead of changing lanes.
- Offline customer-service demo, executable five-minute notebook and manual wiring
  example with behavior comparisons against `attach()`.
- Offline tests, Python 3.10–3.14 CI configuration, opt-in live tests and a recorded
  37-case synthetic smoke battery.
- Banking77 evaluation (770 test cases) with its scripts, recorded answers and report, with
  CC BY 4.0 attribution. Result: the 95% automatic-accuracy target was not reached and the
  fallback did not improve decisions in the llm lane (0 fixed, 2 broken of 30).
- `attach()` fails with a clear message when two routers share a name in one graph.
- A fallback answer that is not a route is recorded as `<invalid route>` in the trace
  instead of verbatim, so model output cannot leak case text into the trace.
- mypy (strict) in CI, `SECURITY.md`, Dependabot, issue/PR templates and project URLs.

Limitations: synchronous execution only; confidence thresholds are not calibrated;
the synthetic battery does not establish accuracy or fallback benefit. The TypeSafe
integration is an alpha dependency. Real-data evaluation and PyPI account configuration
remain release follow-ups; see `docs/RELEASE.md` and `benchmarks/README.md`.
