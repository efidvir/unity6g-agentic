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

## Exact entries

The owner asked for a catalog that is exact for any device TeraFlowSDN supports (2026-11-26). Three things
make it so.

**Every entry says where it comes from.** `provenance` lists each source of the entry's content, exactly
enough to find it again:

- TeraFlowSDN's code at a commit, with a path and a symbol;
- a YANG module at its revision, with a node;
- an RFC or an ITU-T Recommendation;
- a device API as the driver reads or writes it;
- a section of [FW] or of the guide.

**What TeraFlowSDN declares is read from its code, never retyped.** `python -m u6g_catalog import-tfs
<tfs_dir> --source <owner/repo@commit> --binding <entry.yaml>` reads a TeraFlowSDN source tree as text and as
Python syntax trees, running nothing from it (`u6g_catalog/tfs.py`). It writes the result into the `model` of
the controller binding. `--check` reports a difference and writes nothing. The model holds:

- the device types, the kinds of driver and of service, and the KPI sample types;
- which driver serves which device types, and which handler realizes which service type on which drivers;
- the YANG modules of each northbound interface;
- the SLO metric types of the network slice service;
- the radio driver's portfolio, with the products checked against a real device.

**Entries that depend on the controller or the devices are checked against that model.**

- A metric names the KPI sample type that carries it, and the entity and scale it is collected with
  (`teraflowsdn`). Its definition says what each product family reports, and `standard` gives the standard's
  name for the quantity.
- A control parameter names the driver's config rule and field (`teraflowsdn`). Its `families` say what
  each product family's device does with it, as the driver's code does it.
- An action type names the controller operation and the config rule.
- `hardware` records the products the entry has been checked on, and the families still to check. Every
  device-dependent entry starts provisional.

The build reports, under consistency:

- a KPI sample type, a driver or a service type the model does not declare;
- an entry verified on a product the driver does not mark as checked;
- a product or family missing from the portfolio;
- a status that disagrees with its lists.

The first model is the fork's `feat/radio-kpis` at `ddd4aaf`, the radio KPIs included, with 48 device types,
23 kinds of driver, 15 service types and 60 KPI sample types. When the fork merges, the import is repeated
at the merge commit, and again for the ref the lab server runs.

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
- **consistency**:
  - an action type and its bindings disagree on each other or on operations;
  - a predicate names something other than the action's parameters;
  - a verification method is missing;
  - a read-back by controller query relies on a binding whose state does not reflect the device;
  - a flow contract names no flow;
  - two entries claim one code;
  - an entry departs from what TeraFlowSDN declares, or claims a check on hardware the portfolio does not
    record.

The index lists every entry with the SHA-256 digest of its canonical JSON form (RFC 8785), the latest version
of each identity, and the entry of each reason code.

## Snapshot, signature and service

The snapshot is a reproducible archive of the index and every file, so that its digest identifies the
catalog's content. `sign` and `verify` use Ed25519 over that digest. A development machine makes its own key
pair with `keygen`; the private key stays out of the repository. `serve` exposes the index read-only:
`/v1/resolve?ref=`, `/v1/entries`, `/v1/entries/<id>@<version>`, `/v1/latest/<id>`,
`/v1/reason-codes/<code>` and `/v1/health`.

## What making it exact turned up

These come from the radio driver's code at `ddd4aaf`. They are written into the entries as the driver
behaves, and listed in `STATE.md` for the fork:

- **The RFC 8561 view is not RFC 8561's module.** The driver's `/microwave-radio-link` puts the figures in a
  `radio-performance` container, and the coding and modulation in use at `selected-cm`. RFC 8561 has
  `actual-transmitted-level`, `actual-received-level`, `actual-snir`, `actual-xpi` and `actual-tx-cm` on the
  carrier termination, and `selected-cm` only for fixed modulation. The bundled `ietf-microwave-radio-link`
  and `ietf-microwave-types` are reduced copies of the modules.
- **On MultiHaul TG:**
  - the maximum modulation is turned into `link-distance`: Normal when the value contains the characters
    12, Long otherwise;
  - the minimum is left unset;
  - there is no fixed modulation;
  - the transmit power in dBm is written as a power index clamped to 6..31;
  - the frequency snaps to the nearest of four channels.
- **Capacity of radios with no active link.** Where the device reports no active link, as EtherHaul always
  does, the capacity KPI carries the product's nominal maximum from the portfolio.
- **No read-back of the adaptive modulation limits.** The driver's views do not carry the limits, so
  `set-modulation-limits` has no read-back through the controller yet.
- **Values with no RFC 8561 identity.** CeraOS has an 8-QAM profile, which RFC 8561 does not define.

## Open points

- The first entries are those of the transport domain (Table 17-1) and those the tuple needs: 86 entries. The
  reason codes of the runtime's own stages (GEN, ING, PRE, POST, MS, AE) wait on their category: [FW] names
  four, and these codes fit none of them cleanly (`STATE.md`, questions). The families of admission, gates,
  demotion, holds, delegation and bindings come with those components.
- The UNITY-6G KPI each objective KPI serves is named provisionally.
- Publication of the snapshot as an OCI artifact, with its signature as a referrer, comes with the lab's
  registry.
