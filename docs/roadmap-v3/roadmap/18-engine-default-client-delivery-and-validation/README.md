# Stage 18 — Engine-Default Client Delivery and Validation

## Status and epics

Prepared, not filed.
[CF-EPIC-18](../../github-issues/create-forge/CF-EPIC-18.md),
[FT-EPIC-18](../../github-issues/forge-template/FT-EPIC-18.md).

## Entry criteria

Follow each child's direct blockers below. Contract approval unblocks design;
provider publication unblocks adoption. A blocked child must not begin before
its required decision or immutable hand-off is accepted.

## Child work

| Child | Outcome | Direct blockers |
| --- | --- | --- |
| [CF-18.01](../../github-issues/create-forge/CF-18.01.md) | Consume the bounded package line through generic descriptors. | [FT-17.06](../../github-issues/forge-template/FT-17.06.md) |
| [CF-18.02](../../github-issues/create-forge/CF-18.02.md) | Deliver the approved isolation, compatibility, warning and credential-safety contract. | [CF-18.01](../../github-issues/create-forge/CF-18.01.md) |
| [CF-18.03](../../github-issues/create-forge/CF-18.03.md) | Preserve approved destination safety, cancellation and cleanup semantics. | [CF-18.01](../../github-issues/create-forge/CF-18.01.md) |
| [CF-18.04](../../github-issues/create-forge/CF-18.04.md) | Deliver approved dispatch, local-edit preservation, conflict handling, dry-run and rollback. | [CF-18.03](../../github-issues/create-forge/CF-18.03.md) |
| [CF-18.05](../../github-issues/create-forge/CF-18.05.md) | Cover recorded answers, explicit legacy access and approved preview-project recovery. | [CF-18.04](../../github-issues/create-forge/CF-18.04.md) |
| [FT-18.01](../../github-issues/forge-template/FT-18.01.md) | Independently prove provider/client ownership, reproducibility and generated-project compatibility. | [CF-18.02](../../github-issues/create-forge/CF-18.02.md), [CF-18.05](../../github-issues/create-forge/CF-18.05.md) |
| [CF-18.06](../../github-issues/create-forge/CF-18.06.md) | Prove default, override, update, legacy and failure paths against published provider artefacts. | [CF-18.02](../../github-issues/create-forge/CF-18.02.md), [CF-18.05](../../github-issues/create-forge/CF-18.05.md) |
| [CF-18.07](../../github-issues/create-forge/CF-18.07.md) | Require both integrated validations and verify installation, documentation and rollback guidance. | [FT-18.01](../../github-issues/forge-template/FT-18.01.md), [CF-18.06](../../github-issues/create-forge/CF-18.06.md) |

## Exit criteria

All stage-owned children have reviewed completion evidence. Resolve acceptance
criteria through their named owner and keep scope within the approved contracts.
The client release additionally requires both integrated validations and working
engine-native and legacy updates; provider validation is not a new release.

## Non-goals

No unrelated operational work, new archetype outside this roadmap, remote
component registry or plugin system. Contract-only stages make no runtime,
generated-content, dependency, version or release changes.
