# jev-lanes

Confidence-based routing and escalation policies for Jev and LangGraph.

**Early development:** the repository implements confidence-band selection, the
serializable `RouteTrace`, the `Classifier`/`FallbackModel` protocols, offline fakes and
`JevRouter`, which wires the three lanes and a resumable human review into a LangGraph
`StateGraph`, plus default adapters for TypeSafe and any LangChain chat model (bring your
own keys). The adapters are tested offline with fakes only; they have not been run
against the live services, and `langchain-typesafe` itself is an alpha release. The working name is provisional; this project has not been published.

## Why

Routing needs an explicit policy for uncertainty: when to accept a classifier's
decision, ask another model, or request human judgment. This project aims to make
that policy testable and auditable, including resuming a graph after human review.

The planned initial flow is:

```text
Jev Choice -> confidence band
               auto  -> validated Jev route
               llm   -> fallback model -> validated route or human review
               human -> interrupt -> validated human decision -> route
```

The fallback model's benefit must be evaluated. A valid route name alone does not
establish a correct decision. Jev confidence is a distribution statistic, not an
accuracy guarantee; thresholds depend on the task and its consequences.

## Try the current policy locally

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From this checkout:

```bash
uv sync --locked --dev
uv run python examples/policy.py
```

```python
from jev_lanes import Lanes

# Illustrative thresholds, not calibrated defaults.
lanes = Lanes(auto=0.85, llm=0.60)
assert lanes.lane_for(0.95) == "auto"
assert lanes.lane_for(0.70) == "llm"
assert lanes.lane_for(0.40) == "human"
```

## Try the router offline

`examples/router_offline.py` runs all three lanes and a human review resumed with a
checkpointer, using fakes instead of providers:

```bash
uv run python examples/router_offline.py
```

```python
router = JevRouter(
    name="support",
    routes={"orders": "Order status questions", "billing": "Invoices and payments"},
    lanes=Lanes(auto=0.85, llm=0.60),
    classifier=my_classifier,  # implements classify(payload, routes) -> Classification
    fallback=my_fallback,  # implements decide(payload, routes) -> route name or None
)
router.attach(builder, after="intake")  # route names are the target node names
```

- Declare `router.state_key` (here `support_route`) in your graph state schema; it holds
  the serializable `RouteTrace`. Every invocation starts a new episode.
- By default the state's `messages` are sent to the providers; pass `extract=` to send
  something else or to redact. Case text is never stored in the trace or in the
  review request.
- The fallback model abstaining or naming an unknown route escalates to human review.
  Provider failures raise; they are not converted into a low confidence.
- Human review needs a checkpointer and a stable `thread_id`. Resume with
  `Command(resume="<route>")`; an unknown route is rejected and can be sent again.
  Resuming does not classify again.
- Sync only; requires `langgraph>=1.2.12`.

## Use real providers (bring your own keys)

```python
from jev_lanes.adapters import JevClassifier, LangChainFallback

router = JevRouter(
    name="support",
    routes={"orders": "...", "billing": "...", "other": "Anything else."},
    lanes=Lanes(auto=0.85, llm=0.60),
    classifier=JevClassifier(),  # reads TYPESAFE_API_KEY
    fallback=LangChainFallback("openai:gpt-4.1-mini", temperature=0),
)
```

`JevClassifier` asks TypeSafe a `Choice` whose criteria are your routes (add an `other`
route when they may not cover every input). `LangChainFallback` takes a `BaseChatModel`
or an `init_chat_model` string; install the provider package yourself (for example
`langchain-openai`) and set that provider's key. Keys are never stored or forwarded by
this package. The case text is sent to TypeSafe and, for medium-confidence cases, to the
fallback provider. `examples/byok.py` is a complete example; it calls real services and
is not run in CI.

The fallback model is asked for a route name or `ABSTAIN` in plain text, and the reply
is checked against your routes: anything else escalates to human review.

## The lane policy

Thresholds must satisfy `0 <= llm < auto <= 1`. Equality with either threshold
selects the higher band. Invalid confidence raises an error; a provider failure
is not treated as a low-confidence decision. The package itself never calls external
services; only the providers you inject do.

## Development

```bash
uv run --offline --no-sync ruff check .
uv run --offline --no-sync ruff format --check .
uv run --offline --no-sync pytest
uv build
```

Install dependencies with `uv sync --locked --dev` before running offline checks.
The CI workflow targets Python 3.10–3.14. Distribution builds require a cached
build backend or network access.

## Repository

- `src/jev_lanes/`: public policy primitives, with type annotations
  (`lanes`, `trace`, `protocols`, `router`, `adapters`, and `testing` fakes for offline tests).
- `tests/`: deterministic offline tests.
- `examples/`: runnable policy and offline router examples, a BYOK example that needs
  keys, and a planned customer-service demo.
- `benchmarks/`: evaluation plan; no performance claims yet.
- [Decisions](docs/DECISIONS.md): accepted choices, open questions and ADR index.
- [Implementation plan](docs/PLAN.md): MVP and follow-up scope.
- [Glossary](GLOSSARY.md): domain terminology.
- [Contributing](CONTRIBUTING.md): local workflow and evaluation expectations.

## Naming and related work

[`langgraph-jev-router`](https://pypi.org/project/langgraph-jev-router/) is an existing
third-party project. This is a separate project centered on an explicit three-band
escalation policy. `jev-lanes` returned HTTP 404 from PyPI's public project JSON
endpoint on 2026-10-19; that is not a reservation or publication guarantee.

## References

- [Official LangChain TypeSafe integration](https://docs.langchain.com/oss/python/integrations/providers/typesafe)
- [TypeSafe confidence guidance](https://docs.typesafe.ai/confidence)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

MIT licensed. Independent project; not affiliated with TypeSafe or LangChain.
