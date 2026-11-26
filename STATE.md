# STATE.md

## Now
- Date, session author: 2026-11-25, Claude (AI agent), for the owner of the framework
- Working on: the rework the owner asked for on 2026-11-26. Work item 0.7 becomes the path to the real
  TeraFlowSDN on the lab server cersrv-029, with a proxy that injects the failure behaviors; work item 0.4
  becomes exact, generated from TeraFlowSDN's sources and YANG; the radio KPIs go into the TeraFlowSDN fork
- Next: the route into cersrv-029, then the TeraFlowSDN adapter, and aerOS beside the controller

## Items
| ID | Status (open, in progress, done, blocked) | Evidence or blocker | Updated |
|----|-------------------------------------------|---------------------|---------|
| 0.1 | done | make setup and make check pass locally (Checks below) and in the pipeline: runs 45612680111 (push) and 45612688927 (pull request #1), both success | 2026-11-25 |
| 0.2 | in progress | the tuple's contracts are done and checked, provisional until [IMPL] 3.2 (pull request #2): make check passes locally (Checks below) and in the pipeline: runs 45619948464 (push) and 45619959912 (pull request #2), both success; the rest of Table 26-1 comes with the items that use it | 2026-11-25 |
| 0.3 | done | make check passes locally (Checks below) and in the pipeline: runs 45620156774 (push) and 45620208026 (pull request #3), both success; 26 tests, 8 of them property tests over generated condition trees: structure, declared operands, depth limit, results | 2026-11-25 |
| 0.7 | in progress | reworked by the owner's ruling of 2026-11-26: the controller is the real TeraFlowSDN on cersrv-029, and a proxy in front of its northbound interface injects the five failure behaviors; the mock of pull request #4 is withdrawn; blocked on the route into the server | 2026-11-26 |
| 0.4 | in progress | reworked by the owner's ruling of 2026-11-26 (pull request #5, now on #3): the controller binding holds the model u6g-catalog import-tfs reads from the TeraFlowSDN fork at ddd4aaf (48 device types, 23 kinds of driver, 15 service types, 60 KPI sample types, the driver and handler registries, the YANG of the northbound interfaces, the SLO metric types, the radio portfolio); every entry has its provenance; the radio metrics, parameters and actions name their KPI types, config rules and per-family behaviour, each provisional on hardware; the build checks them against the model; 86 entries; the guide's Table 17-1 and examples follow in its next version | 2026-11-26 |
| 1.1 | open | | 2026-11-25 |
| 1.2 | open | | 2026-11-25 |
| 1.3 | open | authority read from a local file until the AI/ML domain exists | 2026-11-25 |
| 1.14 | open | | 2026-11-25 |
| 1.4 | open | | 2026-11-25 |
| 1.5 | open | | 2026-11-25 |
| 1.6 | open | | 2026-11-25 |
| 1.7 | open | | 2026-11-25 |
| 1.8 | open | the first tuple: transport link assurance | 2026-11-25 |

## Checks of the last session
- 2026-11-25, branch item-0.1-skeleton, on a development container (Python 3.13, uv 0.11, Rust 1.97, buf 1.75)
- make setup -> exit 0: the workspace synced (17 packages), cargo fetch, buf dep update, pre-commit installed
- make check -> exit 0: pre-commit all hooks passed (buf lint skipped, no .proto files yet); mypy strict, no
  issues in 30 source files; pytest 58 passed; cargo test 1 passed; make gen, nothing to generate; git diff
  clean
- Pipeline, workflow ci, job check -> success on the push of item-0.1-skeleton (run 45611947414) and on
  pull request #1 (run 45611973770)
- Commits re-authored as the owner with their trees unchanged (git rev-parse of each tree), force-pushed with
  lease -> pipeline success on the push (run 45612680111) and on pull request #1 (run 45612688927)
- 2026-11-25, branch item-0.2-contracts, same container (grpcio-tools 1.85.4, datamodel-code-generator 0.102,
  typify 0.10.1, prost-build 0.14)
- The six examples of the guide, completed, validate against the schemas with jsonschema (2020-12, formats
  checked) -> 0 errors each
- make check -> exit 0: pre-commit all hooks passed, buf lint included; mypy strict, no issues in 43 source
  files; pytest 109 passed (52 new: schemas, models, 23 mutations refused by schema and model alike, the
  Protocol Buffers round trip of the four envelopes, the platform-computed fields, the field numbering);
  cargo test 6 passed (5 new: the Rust types read and write the six examples); make gen twice, git diff clean
- Pipeline, workflow ci, job check -> success on the push of item-0.2-contracts (run 45619019112) and on
  pull request #2 (run 45619091662)
- Review against AGENTS.md: optional lists had empty defaults; now required, possibly empty, with no defaults
  (commit "Contracts: arrays and maps of the semantic objects are required") -> make check exit 0
- 2026-11-25, branch item-0.3-cond: make check -> exit 0; pytest 135 passed (26 new for u6g.cond, 8 property
  tests with Hypothesis, 200 to 300 examples each); mypy strict, no issues in 45 source files
- AGENTS.md asks a property test for every guarantee of [FW] touched: on item-0.2-contracts, a test removes
  each required member of the six examples, 314 cases, and the schemas and the models refuse every one
  ([FW] 3.3.2 and 3.3.4); item-0.3-cond rebased on it -> make check exit 0, pytest 449 passed
- 2026-11-26, branch item-0.4-catalog (cryptography 50, rfc8785 0.1): python -m u6g_catalog build catalog
  -> 73 entries, no findings; keygen, sign and verify of the snapshot -> the signature holds; 23 tests:
  the ten kinds present, Table 17-1 resolving, every reference and reason code of the examples
  resolving, eleven breaches each reported under its rule, the snapshot reproducible and its signature
  refusing a changed snapshot, another key and a forged signature, the REST service -> make check exit 0
- 2026-11-26, the catalog restacked on item-0.3-cond (the mock controller's commit dropped; httpx moved to the
  dev group for the catalog service's tests) -> make check exit 0, pytest 483 passed
- 2026-11-26, the exact catalog: python -m u6g_catalog import-tfs on the fork's feat/radio-kpis at ddd4aaf ->
  48 device types, 23 kinds of driver, 15 service types, 60 KPI sample types, 22 driver and 28 handler
  registrations, 6 northbound interfaces with YANG, 31 radio products (MH-T261 checked); build -> 86 entries,
  no findings; 12 new tests (the reader on a small tree, import and its drift check, the binding against the
  fork, provenance everywhere, seven new breaches) -> pre-commit, mypy strict (51 files), pytest 495 passed,
  cargo test, make gen with no drift
- 2026-11-26, the fork efidvir/teraflowsdn, branch feat/radio-kpis (pull request #2): device/tests/
  test_driver_ceragon.py -> 29 passed (6 new); kpi_sample_types.proto compiled with grpcio-tools, the
  driver's 20 KPI constants equal to the enum

## Documents delivered
- UNITY6G_Agentic_Implementation_Guide_v1.3.docx, version 1.3, 2026-11-26, 223 pages: the real TeraFlowSDN of
  the lab with a fault proxy where version 1.2 had a mock controller (Sections 19.6 and 19.9, Chapters 20, 22
  and 25, Annex G), the exact catalog (Sections 11.4 and 17.1, Table 17-1), the radio KPIs and the Monitoring
  System as the only path of the controller's telemetry to the Data Continuum (Section 5.6), the RFC 8561
  modulation identities in the examples, and the service models TeraFlowSDN's interfaces implement (RFC 8466
  and RFC 8299)
- UNITY6G_Agentic_Implementation_Guide_v1.2.docx, version 1.2, 2026-11-25: the real, emulated and simulated
  forms of each component per environment (Section 19.9), the connection to the components of others
  (Section 19.10), contract suites at the boundary (Section 20.7), OCUDU in the lab, the dependencies of the
  testbed (Section 22.3), the sizing of a development machine (Section 2.3)

## Questions for the owner
- 2026-11-22 The current file of [IMPL] version 3.2, whose Annex A gives the schemas of item 0.2 (guide
  Section 23.4, question 1) -> open
- 2026-11-25 The license of the platform's code, which the LICENSE file records (question 11) -> open
- 2026-11-25 The first tuple: transport link assurance, the guide's reference agent, or a contributed logic
  of the owner's choice -> open; link assurance assumed
- 2026-11-25 Whether the reference implementation of the IDMO and the DMOs runs in containers (question 12)
  -> open
- 2026-11-25 Emulators in the lab for many UEs, radio units and radio channels (question 13) -> open
- 2026-11-26 The config rules of the radio-link parameters in the TeraFlowSDN driver of the radios -> answered
  by the driver's README in the fork: /interface[name=<if>]/radio with tx_power_dbm, frequency_mhz,
  channel_bandwidth_mhz, atpc_enabled and the others, and /interface[name=<if>]/acm with min_modulation,
  max_modulation and adaptive_enabled
- 2026-11-26 How the transport adapter learns the interface version of TeraFlowSDN, which the tfs-api does
  not report -> open: the ref of the fork deployed on cersrv-029 is the first source, for work item 1.7
- 2026-11-26 The category of the reason codes of the runtime's own stages (GEN, ING, PRE, POST, MS, AE):
  [FW] Section 3.6 names decision, mediation, actuation and lifecycle -> open; those codes wait
- 2026-11-26 The UNITY-6G KPIs that kpi/link-availability and kpi/link-capacity-ratio serve, named
  Availability and Capacity for now -> open
- 2026-11-26 The route into cersrv-029, whose SSH key is on the owner's laptop: a GitHub Actions runner on the
  server tied to a private repository, or work through the laptop -> the laptop, the owner's choice; taking
  over a computer leaves terminals click-only, so the owner runs a read-only probe
  (Downloads/cersrv029_probe.sh) and the output comes back through the Downloads folder; the runner stays the
  lasting route for deploying and testing on the server -> open
- 2026-11-26 [IMPL] version 3.2, for Annex B, whose fields the exact catalog follows -> open; the owner is
  looking for the file
- 2026-11-26 Which features of the radio driver were exercised on the MultiHaul MH-T261: the portfolio marks the
  product's API as checked, and the catalog marks an entry verified only for what was exercised; until then
  every device-dependent entry is provisional -> open
- 2026-11-26 What the radio driver does at ddd4aaf that departs from the standards or the catalog's meaning,
  to fix in the fork -> open:
  - its RFC 8561 view uses a radio-performance container and selected-cm where RFC 8561 has the
    carrier-termination leaves and actual-tx-cm, and it bundles reduced copies of the two modules;
  - on MultiHaul TG, the maximum modulation becomes link-distance (Normal when the value contains 12), the
    minimum is left unset, the transmit power in dBm is written as a power index clamped to 6..31;
  - the capacity KPI reports the product's nominal maximum where the device reports no active link;
  - the adaptive modulation limits cannot be read back through the controller
- 2026-11-25 The permitted depth of conditions, which [FW] Section 3.5.18 leaves to [IMPL]: three levels of
  groups assumed, a single comparison being depth 0 -> open
- 2026-11-25 The protos of Annex F keep their names as written, and buf lint leaves out five naming rules of
  STANDARD; the alternative is the STANDARD names (prefixed enum values, ConflictFabricService, SubmitRequest)
  before contributors build on them -> open; kept as written

## Decision log (append only)
- 2026-11-25 The platform's code is hosted on GitHub, in the owner's account, repository unity6g-agentic,
  with GitHub Actions for the checks (source: owner)
- 2026-11-25 Tuple first: the first milestone is one tuple closing its loop on a development machine against
  the simulated controller, then against TeraFlowSDN. The order becomes 0.1, 0.2 (the tuple's contracts),
  0.3, 0.7, 0.4 (the transport entries), 1.1, 1.2, 1.3 (authority from a local file), 1.14, 1.4, 1.5, 1.6,
  1.7, 1.8; the Kubernetes environment (0.6), the agent host, admission, the registry and evaluation follow
  the milestone (source: owner) [replaces: the order of guide Section 25.8]
- 2026-11-25 OCUDU is the RAN substrate of the lab, emulated where radios are missing (source: owner)
- 2026-11-25 The skeleton departs from guide Section 26.2 where the tools need it on an empty tree: buf
  generate runs when proto/ holds files; cargo commands take the manifest of runtime/rust; pre-commit runs
  through uv; make check also runs the Rust tests; the pipeline has the check stage until items 0.8 and 0.6;
  the LICENSE file waits on the owner's choice (source: finding)
- 2026-11-25 Commits carry the owner's identity: Efi Dvir, with the address
  22244452+efidvir@users.noreply.github.com that GitHub links to the account efidvir; a trailer names the AI
  agent as co-author. Each session sets this identity in the git configuration of its clone (source: owner)
- 2026-11-25 Work item 0.2 comes in two parts: the tuple's contracts now (descriptor, envelopes, runtime
  configuration, logic service, fabric, and the code generated from them); the rest of Table 26-1 with the
  items that use it (source: finding)
- 2026-11-25 Generation needs no network: Python protobuf and gRPC code from the protoc of grpcio-tools with
  mypy-protobuf, Rust from typify and from prost with a vendored protoc; uv.lock and Cargo.lock pin every
  version; buf keeps lint and the breaking-change check (source: finding) [replaces: buf.gen.yaml of guide
  Section 26.2]
- 2026-11-25 The Protocol Buffers form of the semantic objects, package u6g.impl.v1, is generated from the
  envelope schemas by u6g.tools.gen_proto with a lossless mapping and field numbers locked in
  semantic.lock.json (source: finding)
- 2026-11-25 Python protobuf modules live at the path of their package (u6g.logic.v1); the Pydantic models
  stay in u6g.generated; u6g.contracts is the entry point (source: finding)
- 2026-11-25 Schemas mark the fields the platform computes with readOnly, and every optional array declares
  an empty default (source: finding)
- 2026-11-25 Arrays and maps of the semantic objects are required, possibly empty, and no schema gives an
  absent field a default, as AGENTS.md rules (source: review) [replaces: every optional array declares an
  empty default]
- 2026-11-25 The condition evaluator uses the three-valued logic of Kleene: a missing value or values that
  cannot be ordered make a comparison unknown, every caller acts only on a condition that holds, and a result
  decided with values missing stays the same when they arrive (source: finding)
- 2026-11-25 Conditions nest at most three levels of groups, a provisional value until [IMPL] sets the
  permitted depth (source: finding)
- 2026-11-26 The catalog lives at catalog/<id>/<version>.yaml with a manifest per area; an entry's owner is
  its area's; a reason code's entry is named after the code; the codes of contributed decision logic
  live in their domain's area (source: finding)
- 2026-11-26 The snapshot of the catalog is a reproducible archive signed with Ed25519 over its digest;
  development machines make their own keys; OCI publication comes with the lab's registry (source:
  finding)
- 2026-11-26 Work item 0.7 targets the real TeraFlowSDN on the lab server cersrv-029. A proxy in front of its
  northbound interface injects rejection, timeout, silence, a change of interface version and an
  acknowledgement without effect, for the tests of the failure paths (source: owner) [replaces: the mock
  controller of work item 0.7]
- 2026-11-26 The type catalog is exact: its entries are generated from TeraFlowSDN's protos and registries and
  from YANG, for any device TeraFlowSDN supports, each with its provenance; entries checked on a real device
  are marked verified (the MultiHaul MH-T261 today), the others provisional until tested on hardware
  (source: owner)
- 2026-11-26 Radio quality reaches TeraFlowSDN as KPIs: KPI sample types 801 to 814 in the fork, streamed by
  the Ceragon driver; polling of device state may be added if a contributor needs it (source: owner)
- 2026-11-26 The Monitoring System is the only publisher of transport observations on the Data Continuum: it
  reads TeraFlowSDN's telemetry and publishes observation envelopes on aerOS, so every consumer receives
  them with the Monitoring System's guarantees (source: owner)
- 2026-11-26 aerOS, the Data Continuum of UNITY-6G, is deployed beside TeraFlowSDN on cersrv-029's MicroK8s,
  its data fabric first; an SRS RAN domain may follow (source: owner)
- 2026-11-26 The consortium's SharePoint is read-only for this work (source: owner)
- 2026-11-26 The implementation documents follow the code: a departure or a gap found while implementing is
  written into the guide and, where it concerns it, into [IMPL] (source: owner)
- 2026-11-26 Every catalog entry carries its provenance; what TeraFlowSDN declares enters the catalog through
  u6g-catalog import-tfs, read from its code at a named commit; metrics, parameters and actions name the KPI
  type, config rule or operation that realizes them and the build checks them against that model; device-
  dependent entries carry their status on hardware (source: owner, the realization a finding)
- 2026-11-26 Modulation values in the catalog are the coding-modulation identities of ietf-microwave-types
  (RFC 8561); a family's own values, as CeraOS's mrmc profiles, are listed with that family (source: finding)
- 2026-11-26 Work item 0.4 goes on top of 0.3: the catalog needs no controller, so pull request #5 no longer
  stacks on the withdrawn #4 (source: finding)

## Provisional contracts
- schemas/common/defs.schema.json, schemas/descriptor/descriptor.schema.json and
  schemas/envelope/{observation,insight,intent,execution}.schema.json stand in for [IMPL] Annex A until work
  item D.3; their source is the guide: Sections 4.3, 5.4, 6.6, 7.11 and 8.8, and Annex B
- schemas/runtime/runtime-config.schema.json stands for guide Annex F.11 until [IMPL] or a design note
  settles it
- proto/u6g/common/v1/common.proto and proto/u6g/logic/v1/logic.proto (guide Annex F.1) and
  proto/u6g/fabric/v1/fabric.proto (Annex F.4), until [IMPL] or a design note settles them
- proto/u6g/impl/v1/semantic.proto is generated from the provisional envelope schemas and follows them
- schemas/catalog/*.schema.json, the ten kinds of catalog entry, stand in for [IMPL] Annex B until work item
  D.3; their source is [FW] Section 3.6 and guide Section 11.4
