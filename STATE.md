# STATE.md

## Now
- Date, session author: 2026-11-25, Claude (AI agent), for the owner of the framework
- Working on: 0.2 Schemas and the generation of code, the tuple's contracts, done in pull request #2, stacked
  on pull request #1; both await the owner's review
- Next: 0.3 Condition evaluator u6g.cond

## Items
| ID | Status (open, in progress, done, blocked) | Evidence or blocker | Updated |
|----|-------------------------------------------|---------------------|---------|
| 0.1 | done | make setup and make check pass locally (Checks below) and in the pipeline: runs 45612680111 (push) and 45612688927 (pull request #1), both success | 2026-11-25 |
| 0.2 | in progress | the tuple's contracts are done and checked, provisional until [IMPL] 3.2 (pull request #2): make check passes locally (Checks below) and in the pipeline: runs 45619019112 (push) and 45619091662 (pull request #2), both success; the rest of Table 26-1 comes with the items that use it | 2026-11-25 |
| 0.3 | open | | 2026-11-25 |
| 0.7 | open | the transport northbound subset first | 2026-11-25 |
| 0.4 | open | the transport entries first | 2026-11-25 |
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

## Documents delivered
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

## Provisional contracts
- schemas/common/defs.schema.json, schemas/descriptor/descriptor.schema.json and
  schemas/envelope/{observation,insight,intent,execution}.schema.json stand in for [IMPL] Annex A until work
  item D.3; their source is the guide: Sections 4.3, 5.4, 6.6, 7.11 and 8.8, and Annex B
- schemas/runtime/runtime-config.schema.json stands for guide Annex F.11 until [IMPL] or a design note
  settles it
- proto/u6g/common/v1/common.proto and proto/u6g/logic/v1/logic.proto (guide Annex F.1) and
  proto/u6g/fabric/v1/fabric.proto (Annex F.4), until [IMPL] or a design note settles them
- proto/u6g/impl/v1/semantic.proto is generated from the provisional envelope schemas and follows them
