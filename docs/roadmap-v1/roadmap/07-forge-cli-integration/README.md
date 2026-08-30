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
- [x] [**CF-07.06 — Create end-to-end CLI generation tests**](https://github.com/Sandsy09/create-forge/issues/51)
  ([ADR 0016](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0016-end-to-end-reference-client-tests.md))

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
rather than ever reaching staging.

CF-07.06 (ADR 0016) closes the epic with real, CI-enforced coverage of the
default `new` path as users experience it: the actual `create-forge` console
script, run against `forge-template`'s latest released tag, its `_tasks`,
and the generated project's own `uv run poe check` -- a new `e2e` marker and
CI job, distinct from `network`, since it costs well over a minute. Two of
the issue's seven acceptance criteria could not be met -- generating through
the *public engine* against a *released* engine-and-assets unit -- because
neither exists yet: `forge-template` has no `0.2.x` release and its
production catalogue stays empty until
[FT-08.02 / forge-template#41](https://github.com/Sandsy09/forge-template/issues/41).
Those two criteria carried forward verbatim to **CF-08.04**, filed under
[CF-EPIC-08](https://github.com/Sandsy09/create-forge/issues/39) and blocked
on the same two things at the time. Both blockers have since resolved --
[FT-08.02 / forge-template#41](https://github.com/Sandsy09/forge-template/issues/41)
shipped the production catalogue, and
[#9](https://github.com/Sandsy09/create-forge/issues/9) published a released
engine range -- and CF-08.04 is complete
([ADR 0020](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0020-engine-path-end-to-end-tests.md)).
See the canonical
[end-to-end tests contract](https://github.com/Sandsy09/create-forge/blob/main/docs/end-to-end-tests.md).
The atomic cutover that replaces both the v0.1.x registry seam and
`--engine-preview` stays gated on
[#9](https://github.com/Sandsy09/create-forge/issues/9).

## Stage completion rule

Both repositories' work is complete. Stage 07 is closed.

- [x] Repo-local issues are complete or explicitly deferred.
- [x] Cross-repository blockers are resolved.
- [x] Public contracts changed by this stage are documented/versioned.
- [x] No implementation concern is duplicated across repositories.
