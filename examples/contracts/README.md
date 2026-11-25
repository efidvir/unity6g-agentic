# Examples of the contracts

The examples of the implementation guide, complete, so that the schemas and the generated models are tested
against them (work item 0.2).

| File | Source in the guide | Schema |
|------|---------------------|--------|
| `descriptor/link-assurance.yaml` | Annex B, the descriptor of the link-assurance agent | `schemas/descriptor/descriptor.schema.json` |
| `envelope/observation.json` | Section 5.4 | `schemas/envelope/observation.schema.json` |
| `envelope/insight.json` | Section 6.6 | `schemas/envelope/insight.schema.json` |
| `envelope/intent.json` | Section 7.11 | `schemas/envelope/intent.schema.json` |
| `envelope/execution.json` | Section 8.8 | `schemas/envelope/execution.schema.json` |
| `runtime/runtime-config.de.yaml` | Annex F.11, a Decision Engine | `schemas/runtime/runtime-config.schema.json` |

The guide abridges some values with an ellipsis: identities of records, digests, the trace context, the token
of a verdict and the signature of the descriptor. Here they are completed with values of the right form, kept
consistent across the files: the insight's model digest is the one the descriptor pins, the intent cites the
insight, and the execution cites the intent and its correlation. The digests and the signature are placeholders
until the descriptor toolchain computes them (work item 0.5).
