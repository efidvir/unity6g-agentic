# unity6g-agentic
AI-Native agentic tuples for the UNITY-6G project

This repository holds the platform of the UNITY-6G agentic framework: the capability runtime that carries every
tuple of Monitoring System, Analytics Engine, Decision Engine and Actuator, the descriptor toolchain, the agent
host of the DMOs, the platform services of the AI/ML domains, the agent-support module beside the IDMO, the
conflict mediator, the adapters and the twin service. Contributors write the logic of a capability; the platform
runs everything around it.

The work starts with the tuple: the first milestone is one tuple closing its loop on a development machine
against the simulated transport controller, then against TeraFlowSDN. `STATE.md` gives where the work stands and
the next item.

## Documents

- **[FW]** The AI-native agentic framework of UNITY-6G: framework specification, version 8. Concepts.
- **[IMPL]** Implementation specification, version 3.2. Formats and interfaces.
- **[INST]** Autonomous agent tuple instantiation specification, version 1.5.
- **The implementation guide**, version 1.2. Practice: the tools, the components, the backlog (Chapter 25) and
  the first commits of this repository (Chapter 26).

## Commands

```text
make setup        # uv sync, cargo fetch, buf dependencies, pre-commit hooks
make gen          # regenerate code from schemas/ (check in the result)
make check        # lint, types, unit and property tests, regeneration check
make dev-up       # local environment (work item 0.6)
make it           # integration sequences on the local environment
make conformance  # conformance suite with fault injection
make bench        # overhead benchmarks against the previous release
```

The tools: Python 3.12 or later with uv, Rust 1.85 or later, buf, and make.

## Layout

```text
schemas/ proto/ openapi/ crds/   the contracts; code is generated from them
catalog/                         the type catalog as code
runtime/python/u6g/              runtime, sdk, ms, ae, de, act, cond, state, authority
runtime/rust/                    u6g-runtime-rt (real-time core), u6g-types, u6g-typegen
services/                        admission, registry, catalog, eval, agenthost, idmo-ext, mediator, dt,
                                 mockctl, mockorch
adapters/                        sources, southbound, ran, idmo
cli/                             the u6g command line
conformance/                     the conformance suite, fault injection, hostile images
deploy/                          dev, lab, testbed
observability/                   Collector configurations, rules, dashboards
examples/agents/                 reference tuples, link assurance first
docs/                            the documentation site, design notes in docs/design/
tests/                           checks of the repository itself
```

Coding agents read `AGENTS.md` first.
