# Security policy

`jev-lanes` is an experimental release candidate and is not published yet. Only the latest
version receives fixes.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Use GitHub's private
reporting: *Security → Report a vulnerability* on
[EricMariano/jev-lanes](https://github.com/EricMariano/jev-lanes/security/advisories/new).
Include the version, a minimal reproduction and the impact you see. Expect an
acknowledgement within a few days; this is a volunteer project and no response time is
guaranteed.

## Scope and data handling

- The package never calls external services by itself. The providers you inject do: the
  conversation text goes to TypeSafe (the classifier) and to your chat model's provider.
  By default the classifier receives only customer and assistant text, not tool calls or
  tool results; use `extract=` to restrict or redact what leaves your environment.
- Keys are read from the environment by the provider libraries; this package never stores
  or forwards them. Never put keys in issues, logs or example files.
- `GateTrace` does not contain message text or tool arguments. The graph state and
  checkpoints do (`messages`); their retention is your checkpointer's policy.
- The gate decides whether a tool may run, not with which arguments. The model chooses the
  arguments and the customer's replies are untrusted input to the model: validate arguments
  inside each tool and keep irreversible tools behind a high `min_confidence`.
- Classifier confidence is a statistic, not a security control. Do not use it as the only
  protection for actions that need authentication or authorization.
- Out of scope: vulnerabilities in LangGraph, LangChain, TypeSafe or a model provider;
  report those upstream.
