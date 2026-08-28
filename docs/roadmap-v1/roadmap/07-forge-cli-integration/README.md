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
- [x] [**CF-07.04 — Implement safe filesystem generation**](https://github.com/Sandsy09/create-forge/issues/50)
  ([ADR 0015](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0015-staged-filesystem-generation.md))
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
established.

CF-07.04 completes that flag with real filesystem orchestration
(ADR 0015): a new engine-free `src/create_forge/staging.py` stages a
successful engine render adjacent to its destination and finalises it by
atomic rename, and wraps the existing Copier path with cleanup after a
failure -- Copier's `_tasks` (`uv sync`, `pre-commit install`) bake `dst`'s
absolute path into `.venv`/hooks, so that path is cleaned up rather than
staged. It also moves the development engine pin forward once, within the
same unreleased `0.2.0` contract, to adopt `forge-template`'s
generated-project validation (`render_project` now calls
`validate_rendered_project` before returning) -- see the canonical
[filesystem generation contract](https://github.com/Sandsy09/create-forge/blob/main/docs/filesystem-generation.md).
`--engine-preview` still deterministically fails today, now at validation
rather than ever reaching staging. CF-07.06 remains open; the atomic
cutover that replaces both the v0.1.x registry seam and `--engine-preview`
stays gated on [#9](https://github.com/Sandsy09/create-forge/issues/9).

## Stage completion rule

The `forge-template` counterpart is complete. The shared stage remains open
for the one remaining `create-forge` issue above.

- [ ] Repo-local issues are complete or explicitly deferred.
- [ ] Cross-repository blockers are resolved.
- [ ] Public contracts changed by this stage are documented/versioned.
- [ ] No implementation concern is duplicated across repositories.
