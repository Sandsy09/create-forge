# Stage 15 — Engine-Default Provider Contracts

## Status and epics

Prepared, not filed.
[FT-EPIC-15](../../github-issues/forge-template/FT-EPIC-15.md).

## Entry criteria

Follow each child's direct blockers below. Contract approval unblocks design;
provider publication unblocks adoption. A blocked child must not begin before
its required decision or immutable hand-off is accepted.

## Child work

| Child | Outcome | Direct blockers |
| --- | --- | --- |
| [FT-15.01](../../github-issues/forge-template/FT-15.01.md) | Account for every supported behaviour, generated concern and explicit exclusion. | None |
| [FT-15.02](../../github-issues/forge-template/FT-15.02.md) | Specify versioned metadata, output ownership and reproducible old/new render requirements. | [FT-15.01](../../github-issues/forge-template/FT-15.01.md) |
| [FT-15.03](../../github-issues/forge-template/FT-15.03.md) | Assign concerns to Foundation, archetypes, capabilities and platforms; identify necessary extension points. | [FT-15.01](../../github-issues/forge-template/FT-15.01.md) |
| [FT-15.04](../../github-issues/forge-template/FT-15.04.md) | Classify public API/protocol changes and approve the provider acceptance matrix. | [FT-15.02](../../github-issues/forge-template/FT-15.02.md), [FT-15.03](../../github-issues/forge-template/FT-15.03.md) |

## Exit criteria

All stage-owned children have reviewed completion evidence. Resolve acceptance
criteria through their named owner and keep scope within the approved contracts.

## Non-goals

No unrelated operational work, new archetype outside this roadmap, remote
component registry or plugin system. Contract-only stages make no runtime,
generated-content, dependency, version or release changes.
