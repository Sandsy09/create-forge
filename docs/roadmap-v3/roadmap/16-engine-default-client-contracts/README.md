# Stage 16 — Engine-Default Client Contracts

## Status and epics

Filed and open.
[CF-EPIC-16](https://github.com/Sandsy09/create-forge/issues/152).

## Entry criteria

Follow each child's direct blockers below. Contract approval unblocks design;
provider publication unblocks adoption. A blocked child must not begin before
its required decision or immutable hand-off is accepted.

## Child work

| Child | Outcome | Direct blockers |
| --- | --- | --- |
| [CF-16.01](https://github.com/Sandsy09/create-forge/issues/155) | Settle defaults, configuration precedence, explicit legacy access, override security and flag deprecations. | [FT-15.04](https://github.com/Sandsy09/forge-template/issues/149) |
| [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156) | Settle engine updates, legacy and preview-project handling, conflicts, dry-run, rollback, Git and hooks. | [CF-16.01](https://github.com/Sandsy09/create-forge/issues/155) |
| [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) | Define release sequencing, support windows and executable release gates. | [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156) |

## Exit criteria

All stage-owned children have reviewed completion evidence. Resolve acceptance
criteria through their named owner and keep scope within the approved contracts.

## Non-goals

No unrelated operational work, new archetype outside this roadmap, remote
component registry or plugin system. Contract-only stages make no runtime,
generated-content, dependency, version or release changes.
