# Contracts and the generation of code

Design note of work item 0.2. Status: provisional contracts, until [IMPL] version 3.2 arrives.

## What is a source and what is generated

| Source (edited by hand) | Generator | Output (checked in) |
|---|---|---|
| `schemas/**/*.schema.json`, JSON Schema 2020-12 | `u6g.tools.gen_models` (datamodel-code-generator) | Pydantic models in `runtime/python/u6g/generated/` |
| `schemas/envelope/*.schema.json` | `u6g.tools.gen_proto` | `proto/u6g/impl/v1/semantic.proto` and its `semantic.lock.json` |
| `proto/**/*.proto` | `u6g.tools.gen_grpc` (the protoc of grpcio-tools, mypy-protobuf) | `runtime/python/u6g/<service>/v1/*_pb2.py`, `*_pb2_grpc.py` and their `.pyi` stubs |
| `schemas/**/*.schema.json` | `u6g-typegen` (typify) | `runtime/rust/u6g-types/src/contracts.rs` |
| `proto/**/*.proto` | `u6g-typegen` (prost, the protoc of protoc-bin-vendored) | `runtime/rust/u6g-types/src/proto/` |

`make gen` runs the four generators in this order; `make check` runs it and fails when the result differs from
what is checked in. No generator needs the network, and every version is pinned by `uv.lock` and
`Cargo.lock`, so that the same sources give the same output on a laptop, in the pipeline and in the lab.

In Python, `u6g.contracts` is the entry point: it re-exports the main models (`AgentDescriptor`,
`Observation`, `Insight`, `Intent`, `ExecutionFeedback`, `RuntimeConfig`) and converts the semantic objects
to and from their Protocol Buffers form.

## The schemas

- One file per contract, with the shared types in `schemas/common/defs.schema.json`. Every name of a `$defs`
  entry is unique across the files, because the Rust generator bundles them into one set of types.
- Shared string types (catalog references, durations, digests, identities) carry their pattern, and become
  type aliases in Python, so that fields hold plain strings that are validated.
- Fields that the platform computes carry `readOnly: true` on the property. The Python models keep the mark
  in `json_schema_extra`, and `u6g.contracts.platform_fields()` lists them as JSON Pointers, so that the
  runtime can refuse them from contributed logic (guide Section 3.4).
- Every file says `Provisional:` in its `$comment` and is listed in `STATE.md`. When [IMPL] arrives, its
  definitions replace these files (work item D.3) and the generators run unchanged.

## The Protocol Buffers form of the semantic objects

The logic service carries observations, insights and execution feedback as `u6g.impl.v1` messages (guide
Annex F.1). `gen_proto` writes them from the envelope schemas so that a JSON document maps to a message and
back with nothing lost:

- scalars are `optional`, so that a zero or an empty string stays present; enumerations stay strings;
- `format: date-time` becomes `google.protobuf.Timestamp`; ISO 8601 durations stay strings;
- free-form objects become `google.protobuf.Struct`, objects of strings `map<string, string>`, and a choice
  of types `google.protobuf.Value`;
- an empty list and an absent one are the same in Protocol Buffers, and no schema gives an absent field a
  default (`AGENTS.md`), so every array and map of a semantic object is required, possibly empty; the
  generator refuses an optional one.

The JSON names of the messages are the property names of the schemas, so the proto3 JSON mapping is the
conversion: `u6g.contracts.to_message()` and `from_message()` go through it, and the tests check that the four
examples come back equal after the wire format. Field numbers live in `semantic.lock.json`: a new property
takes the next free number, and a removed one leaves its number and name reserved, so that regeneration keeps
the wire format compatible.

## The protos of guide Annex F

`common.proto`, `logic.proto` and `fabric.proto` are the definitions of Annex F.1 and F.4 as written. `buf lint`
runs the STANDARD rules except five naming rules that the Annex's names depart from: values of nested enums
without the enum's prefix, the services `ConflictFabric` and `RuntimeGateway`, and request and response types
named for what they carry (`Submission`, `Verdict`). `buf` stays the tool for lint and for the breaking-change
check; generation uses the local compilers above.

## Departures from guide Section 26.2

- `buf.gen.yaml` and its remote plugins are gone: the Buf Schema Registry is unreachable from the development
  container behind a proxy where this was built, and may be from the lab; remote plugins would also leave the
  versions of generated code outside the lock files.
- The Python protobuf modules live at the path of their package (`u6g.logic.v1.logic_pb2`), so that their own
  imports resolve; the Pydantic models stay in `u6g.generated`.
- The Rust generator takes the proto directory too, and writes both halves of `u6g-types`.
