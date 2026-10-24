# Security policy

`jev-lanes` is an experimental release candidate (`0.1.0rc1`). Only the latest published
version receives fixes.

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Use GitHub's private
reporting: *Security → Report a vulnerability* on
[EricMariano/jev-lanes](https://github.com/EricMariano/jev-lanes/security/advisories/new).
Include the version, a minimal reproduction and the impact you see. Expect an
acknowledgement within a few days; this is a volunteer project and no response time is
guaranteed.

## Scope and data handling

- The package never calls external services by itself. The providers you inject do:
  the case text is sent to TypeSafe and, for medium-confidence cases, to your fallback
  provider. Use `extract=` to restrict or redact what leaves your environment.
- Keys are read from the environment by the provider libraries; this package never stores
  or forwards them. Never put keys in issues, logs or example files.
- `RouteTrace` and the human-review request do not contain the case text. The graph state
  and checkpoints do (`messages`); their retention is your checkpointer's policy.
- The fallback model's reply is untrusted. It is matched against your route names, and
  anything else escalates to human review and is recorded only as a fixed marker.
- Out of scope: vulnerabilities in LangGraph, LangChain, TypeSafe or a model provider;
  report those upstream.
