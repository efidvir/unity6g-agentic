# UNITY-6G agentic framework, the platform

## What this repository is
The platform of the UNITY-6G agentic framework: the capability runtime, the descriptor toolchain,
the agent host of the DMOs, the platform services of the AI/ML domains, the agent-support module
beside the IDMO, the conflict mediator, the adapters and the twin service.
Concepts: [FW] version 8. Formats: [IMPL]. Practice: the implementation guide version 1.2.

## Read first
1. STATE.md: where the work stands and the next item.
2. Implementation guide, Chapters 23 and 24 (handover and procedure).
3. The guide's chapter for the component you change, and Annex F for its interfaces.

## Commands
make setup        # uv sync, cargo fetch, buf dependencies, pre-commit hooks
make gen          # regenerate code from schemas/ (check in the result)
make check        # lint, types, unit and property tests, regeneration check
make dev-up       # local environment on k3d (one AI/ML domain, the IDMO site, two domains)
make it           # integration sequences of guide Chapter 14 on the local environment
make conformance  # conformance suite with fault injection
make bench        # overhead benchmarks against the previous release

## Rules
- Guardrails are platform code: gates, counters, limits, timers, tokens and submissions live in
  runtime/ and stay out of contributed logic.
- The logic container has no network, identity or credentials; it reaches everything through
  the runtime's gateway, over the sockets of the volume the two containers share.
- Change a schema first, regenerate, then change code. Generated code is checked in.
- The IDMO, the DMOs and their adapter belong to their implementers: add messages and modules
  beside them, and send requests for change as recommendations.
- No default values for absent fields: reject with a diagnostic.
- Every guarantee of [FW] you touch gets a property test naming its clause.
- Secrets come from OpenBao at run time; the repository holds references only.
- Run make check before every commit, and record the commands and results in the merge request.

## When to stop and ask the owner
Concept changes, disagreements between [FW], [IMPL] and the guide, changes to components owned by
others, security, new licenses, and anything that cannot be undone (guide Section 24.5).

## At the end of a session
Update STATE.md: items closed with evidence, items in progress, checks and results, questions and
answers, next item.
