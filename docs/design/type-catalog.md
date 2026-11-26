# The type catalog as code

Design note of work item 0.4. The catalog holds the definitions descriptors refer to ([FW] Section 3.6, guide
Section 11.4). Its schemas are provisional until [IMPL] Annex B arrives.

## Layout

```text
catalog/<area>/area.yaml                 the area's owner and its classes of managed object
catalog/<id>/<version>.yaml              one entry, for example catalog/transport/metric/rsl/1.2.0.yaml
schemas/catalog/<kind>.schema.json       the schema of each of the ten kinds
```

An entry's identity is its area, its kind and its name (`transport/metric/rsl`); entries refer to each other as
`<id>@<version>`, and descriptors and envelopes as `catalog://<id>@<version>`. Every entry states its kind,
identity, version, owner, description and whether it is deprecated. A reason code's entry is named after the
code in lower case (`platform/reason/act-ok` for `ACT-OK`); the codes of contributed decision logic live in
the area of their domain, the framework's in `platform`.

| Kind | What it states besides the header |
|---|---|
| Metric | Object class, definition, value and unit, gauge, counter, state or event, aggregation, source kinds |
| ControlParameter | Object class, value and unit, the bindings that set it, how it is read back |
| ActionType | Target class and parameters, the JSON Schema of its parameters, idempotency, verification methods with their predicates, rollback, operations per binding |
| InsightType | Object class, meaning, the JSON Schema of its payload |
| ObjectiveKpi | Definition, unit, methodology, the UNITY-6G KPI it serves |
| VerificationMethod | Read-back path and typical latency |
| ControllerBinding | Controller, interface and versions, action types, operations, adapter, whether its state reflects the device, rollback route |
| SourceKind | Protocol, acquisition patterns, adapter; read-only by construction |
| ReasonCode | Code, category (decision, mediation, actuation or lifecycle), meaning, who raises it |
| ServiceContract | Contribution (flow or platform service), provider, interface, what a flow carries, where the platform consumes a service |

## The build

`python -m u6g_catalog build catalog --out <dir>` validates and indexes the catalog, and writes nothing if it
finds a breach. Each finding names the file and the rule:

- **schema**: the entry fails the schema of its kind, or its kind is unknown;
- **identity**: the file's path differs from the entry's identity and version, or a reason code's entry is
  named after another code;
- **reference**: a reference does not resolve, or resolves to the wrong kind (a metric's sources are source
  kinds, a parameter is set by bindings, a flow carries metrics, insight types or action types as its flow
  says);
- **area**: the entry's area has no manifest, its owner differs from the area's, or its object class is not
  one of the area's;
- **consistency**: an action type and its bindings disagree on each other or on operations, a predicate names
  something other than the action's parameters, a verification method is missing, a read-back by controller
  query relies on a binding whose state does not reflect the device, a flow contract names no flow, or two
  entries claim one code.

The index lists every entry with the SHA-256 digest of its canonical JSON form (RFC 8785), the latest version
of each identity, and the entry of each reason code.

## Snapshot, signature and service

The snapshot is a reproducible archive of the index and every file, so that its digest identifies the
catalog's content. `sign` and `verify` use Ed25519 over that digest. A development machine makes its own key
pair with `keygen`; the private key stays out of the repository. `serve` exposes the index read-only:
`/v1/resolve?ref=`, `/v1/entries`, `/v1/entries/<id>@<version>`, `/v1/latest/<id>`,
`/v1/reason-codes/<code>` and `/v1/health`.

## Open points

- The first entries are those of the transport domain (Table 17-1) and those the tuple needs: 73 entries. The
  reason codes of the runtime's own stages (GEN, ING, PRE, POST, MS, AE) wait on their category: [FW] names
  four, and these codes fit none of them cleanly (`STATE.md`, questions). The families of admission, gates,
  demotion, holds, delegation and bindings come with those components.
- The UNITY-6G KPI each objective KPI serves is named provisionally.
- Publication of the snapshot as an OCI artifact, with its signature as a referrer, comes with the lab's
  registry.
