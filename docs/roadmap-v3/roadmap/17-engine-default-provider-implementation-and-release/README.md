# Stage 17 — Engine-Default Provider Implementation and Release

## Status and epics

Prepared, not filed.
[FT-EPIC-17](../../github-issues/forge-template/FT-EPIC-17.md).

## Entry criteria

Follow each child's direct blockers below. Contract approval unblocks design;
provider publication unblocks adoption. A blocked child must not begin before
its required decision or immutable hand-off is accepted.

## Child work

| Child | Outcome | Direct blockers |
| --- | --- | --- |
| [FT-17.01](../../github-issues/forge-template/FT-17.01.md) | Expose approved information through the public facade without leaking resource paths. | [CF-16.03](../../github-issues/create-forge/CF-16.03.md) |
| [FT-17.02](../../github-issues/forge-template/FT-17.02.md) | Deliver catalogue-owned selection and compatibility rules. | [CF-16.03](../../github-issues/create-forge/CF-16.03.md) |
| [FT-17.03](../../github-issues/forge-template/FT-17.03.md) | Implement the remaining tooling/content requirements and protect existing output. | [FT-17.02](../../github-issues/forge-template/FT-17.02.md) |
| [FT-17.04](../../github-issues/forge-template/FT-17.04.md) | Supply the approved update inputs and structured failure behaviour. | [FT-17.01](../../github-issues/forge-template/FT-17.01.md) |
| [FT-17.05](../../github-issues/forge-template/FT-17.05.md) | Execute the approved matrix, downstream-facade checks and wheel/sdist audits. | [FT-17.03](../../github-issues/forge-template/FT-17.03.md), [FT-17.04](../../github-issues/forge-template/FT-17.04.md) |
| [FT-17.06](../../github-issues/forge-template/FT-17.06.md) | Record immutable artefacts and the supported client hand-off. | [FT-17.05](../../github-issues/forge-template/FT-17.05.md) |

## Exit criteria

All stage-owned children have reviewed completion evidence. Resolve acceptance
criteria through their named owner and keep scope within the approved contracts.

## Non-goals

No unrelated operational work, new archetype outside this roadmap, remote
component registry or plugin system. Contract-only stages make no runtime,
generated-content, dependency, version or release changes.
