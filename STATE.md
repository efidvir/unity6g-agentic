# STATE.md

## Now
- Date, session author: 2026-11-25, Claude (AI agent), for the owner of the framework
- Working on: 0.1 Repository, layout and tooling, done; pull request #1 awaits the owner's review
- Next: 0.2 Schemas and the generation of code, limited to the tuple's contracts: the descriptor, the
  envelopes of observations, insights, intents and executions, the logic service and the verdicts

## Items
| ID | Status (open, in progress, done, blocked) | Evidence or blocker | Updated |
|----|-------------------------------------------|---------------------|---------|
| 0.1 | done | make setup and make check pass locally (Checks below) and in the pipeline: runs 45612680111 (push) and 45612688927 (pull request #1), both success | 2026-11-25 |
| 0.2 | open | the tuple's contracts first; provisional from guide Annex F until [IMPL] 3.2 arrives | 2026-11-25 |
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

## Provisional contracts
- None yet. Item 0.2 adds the reference definitions of guide Annex F for the tuple, marked provisional, until
  [IMPL] version 3.2 arrives.
