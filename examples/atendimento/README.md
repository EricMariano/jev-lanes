# Customer-service demo

From the repository root:

```bash
uv sync --locked --dev
uv run --offline --no-sync python examples/atendimento/demo.py
```

Four scripted cases run through a real LangGraph with separate orders, billing and
account handlers:

1. High confidence routes directly to orders.
2. Medium confidence asks the fallback, which selects billing.
3. Low confidence pauses for a human, who selects account.
4. Medium confidence with fallback abstention pauses for a human, who selects billing.

Both human reviews first receive an invalid route, catch the validation error and
resume with a valid one. Assertions check that no handler runs before review and that
each case is classified once, including across invalid and valid resume attempts.
Human responses are scripted for a non-interactive demonstration.

The checkpointer is `InMemorySaver`: checkpoints survive between calls in this process,
not process restarts. A deployed application needs a persistent checkpointer and a
stable, unique `thread_id` per conversation. It must also collect the human response
through its own UI before invoking `Command(resume="<route>")` with the same config.

All provider responses are fakes. To use real providers, replace the arguments to
`build_graph()` with `JevClassifier()` and `LangChainFallback(model)` from
`jev_lanes.adapters`, install the model's provider package and supply your own keys.
The messages then leave your environment; use `extract=` on the router to redact them.
The thresholds are illustrative and the example replies do not perform account,
payment or order operations.
