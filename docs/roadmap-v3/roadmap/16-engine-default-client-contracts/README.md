# Stage 16 — Engine-Default Client Contracts

## Status and epics

Prepared, not filed.
[CF-EPIC-16](../../github-issues/create-forge/CF-EPIC-16.md).

## Entry criteria

Follow each child's direct blockers below. Contract approval unblocks design;
provider publication unblocks adoption. A blocked child must not begin before
its required decision or immutable hand-off is accepted.

## Child work

| Child | Outcome | Direct blockers |
| --- | --- | --- |
| [CF-16.01](../../github-issues/create-forge/CF-16.01.md) | Settle defaults, configuration precedence, explicit legacy access, override security and flag deprecations. | [FT-15.04](../../github-issues/forge-template/FT-15.04.md) |
| [CF-16.02](../../github-issues/create-forge/CF-16.02.md) | Settle engine updates, legacy and preview-project handling, conflicts, dry-run, rollback, Git and hooks. | [CF-16.01](../../github-issues/create-forge/CF-16.01.md) |
| [CF-16.03](../../github-issues/create-forge/CF-16.03.md) | Define release sequencing, support windows and executable release gates. | [CF-16.02](../../github-issues/create-forge/CF-16.02.md) |

## Exit criteria

All stage-owned children have reviewed completion evidence. Resolve acceptance
criteria through their named owner and keep scope within the approved contracts.

## Non-goals

No unrelated operational work, new archetype outside this roadmap, remote
component registry or plugin system. Contract-only stages make no runtime,
generated-content, dependency, version or release changes.
