# Stage 17 — Engine-Default Provider Implementation and Release

## Status and epics

Filed and open.
[FT-EPIC-17](https://github.com/Sandsy09/forge-template/issues/142).

## Entry criteria

Follow each child's direct blockers below. Contract approval unblocks design;
provider publication unblocks adoption. A blocked child must not begin before
its required decision or immutable hand-off is accepted.

## Child work

| Child | Outcome | Direct blockers |
| --- | --- | --- |
| [FT-17.01](https://github.com/Sandsy09/forge-template/issues/150) | Expose approved information through the public facade without leaking resource paths. | [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) |
| [FT-17.02](https://github.com/Sandsy09/forge-template/issues/151) | Deliver catalogue-owned selection and compatibility rules. | [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) |
| [FT-17.03](https://github.com/Sandsy09/forge-template/issues/152) | Implement the remaining tooling/content requirements and protect existing output. | [FT-17.02](https://github.com/Sandsy09/forge-template/issues/151) |
| [FT-17.04](https://github.com/Sandsy09/forge-template/issues/153) | Supply the approved update inputs and structured failure behaviour. | [FT-17.01](https://github.com/Sandsy09/forge-template/issues/150) |
| [FT-17.05](https://github.com/Sandsy09/forge-template/issues/154) | Execute the approved matrix, downstream-facade checks and wheel/sdist audits. | [FT-17.03](https://github.com/Sandsy09/forge-template/issues/152), [FT-17.04](https://github.com/Sandsy09/forge-template/issues/153) |
| [FT-17.06](https://github.com/Sandsy09/forge-template/issues/155) | Record immutable artefacts and the supported client hand-off. | [FT-17.05](https://github.com/Sandsy09/forge-template/issues/154) |

## Exit criteria

All stage-owned children have reviewed completion evidence. Resolve acceptance
criteria through their named owner and keep scope within the approved contracts.

## Non-goals

No unrelated operational work, new archetype outside this roadmap, remote
component registry or plugin system. Contract-only stages make no runtime,
generated-content, dependency, version or release changes.
