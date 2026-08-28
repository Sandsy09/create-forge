# Stage 07 — Forge CLI Integration

## Repository ownership

### forge-template — complete

- ~~[**FT-07.05 — Add generated-project validation**](https://github.com/Sandsy09/forge-template/issues/39)~~
  — completed by the canonical
  [validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md),
  [ADR 0030](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0030-generated-project-validation.md),
  and [forge-template PR #77](https://github.com/Sandsy09/forge-template/pull/77).

### create-forge

- Epic: [CF-EPIC-07 / #38](https://github.com/Sandsy09/create-forge/issues/38)
- [x] [**CF-07.01 — Implement shared create pipeline**](https://github.com/Sandsy09/create-forge/issues/49)
  ([ADR 0014](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0014-lazy-engine-reachability.md))
- ~~**CF-07.02 — Implement interactive project creation**~~ — completed before roadmap filing.
- ~~**CF-07.03 — Implement non-interactive CLI parity**~~ — completed before roadmap filing.
- [**CF-07.04 — Implement safe filesystem generation**](https://github.com/Sandsy09/create-forge/issues/50)
- [**CF-07.06 — Create end-to-end CLI generation tests**](https://github.com/Sandsy09/create-forge/issues/51)

## Stage record

CF-07.01 makes the Stage 06 construction/discovery boundary reachable from a
real command for the first time: `src/create_forge/pipeline.py` runs
discover → build → validate → render and returns an in-memory
`GenerationRequest`, called from `new`'s new hidden `--engine-preview` flag
via a lazy, guarded import (ADR 0014) — `forge-template` stays a
development-only dependency, so `cli.py` cannot import it unconditionally
without breaking every real `uvx create-forge` install. The default `new`
path, and every other command, are unchanged. `--engine-preview`
deterministically fails today against `forge-template`'s intentionally empty
production catalogue, the same characterized-failure pattern Stage 06
established. CF-07.04 and CF-07.06 remain open; the atomic cutover that
replaces both the v0.1.x registry seam and `--engine-preview` stays gated on
[#9](https://github.com/Sandsy09/create-forge/issues/9).

## Stage completion rule

The `forge-template` counterpart is complete. The shared stage remains open
for the two remaining `create-forge` issues above.

- [ ] Repo-local issues are complete or explicitly deferred.
- [ ] Cross-repository blockers are resolved.
- [ ] Public contracts changed by this stage are documented/versioned.
- [ ] No implementation concern is duplicated across repositories.
