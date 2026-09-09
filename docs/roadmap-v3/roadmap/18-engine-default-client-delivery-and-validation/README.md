# Stage 18 — Engine-Default Client Delivery and Validation

## Status and epics

Filed and open.
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153),
[FT-EPIC-18](https://github.com/Sandsy09/forge-template/issues/143).

## Entry criteria

Follow each child's direct blockers below. Contract approval unblocks design;
provider publication unblocks adoption. A blocked child must not begin before
its required decision or immutable hand-off is accepted.

## Child work

| Child | Outcome | Direct blockers |
| --- | --- | --- |
| [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) | Consume the bounded package line through generic descriptors. | [FT-17.06](https://github.com/Sandsy09/forge-template/issues/155) |
| [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) | Deliver the approved isolation, compatibility, warning and credential-safety contract. | [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) |
| [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) | Preserve approved destination safety, cancellation and cleanup semantics. | [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) |
| [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) | Deliver approved dispatch, local-edit preservation, conflict handling, dry-run and rollback. | [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) |
| [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) | Cover recorded answers, explicit legacy access and approved preview-project recovery. | [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) |
| [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156) | Independently prove provider/client ownership, reproducibility and generated-project compatibility. | [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159), [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) |
| [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) | Prove default, override, update, legacy and failure paths against published provider artefacts. | [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159), [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) |
| [CF-18.07](https://github.com/Sandsy09/create-forge/issues/164) | Require both integrated validations and verify installation, documentation and rollback guidance. | [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156), [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) |

## Exit criteria

All stage-owned children have reviewed completion evidence. Resolve acceptance
criteria through their named owner and keep scope within the approved contracts.
The client release additionally requires both integrated validations and working
engine-native and legacy updates; provider validation is not a new release.

## Non-goals

No unrelated operational work, new archetype outside this roadmap, remote
component registry or plugin system. Contract-only stages make no runtime,
generated-content, dependency, version or release changes.
