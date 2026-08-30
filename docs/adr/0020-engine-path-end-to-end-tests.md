# 20. Test the public engine path end to end

## Status

Accepted

## Context

[ADR 0016](0016-end-to-end-reference-client-tests.md) built the `e2e` test
tier for CF-07.06 and closed it with exactly half of what the issue asked
for: real, CI-enforced coverage of the default `new` (Copier) path. Its own
Consequences section named the other half explicitly — "the engine path
stays completely uncovered end-to-end... a known, named gap — CF-08.04, not
a silent one." At that time `forge-template` had no released distribution and
its production catalogue was empty, so `--engine-preview` had nothing
installable to render against.

[#9](https://github.com/Sandsy09/create-forge/issues/9)
([ADR 0018](0018-pypi-distribution-and-the-first-engine-range.md)) removed
both blockers: `forge-template 0.3.1` is on PyPI, and `create-forge[engine]`
resolves it as an ordinary, range-bounded optional dependency
(`>=0.3.1,<0.4`). [CF-08.03](0019-cli-archetype-parity-review.md) then
confirmed the engine path produces structurally sound output for both
archetypes at the payload level. [#85 / CF-08.04](https://github.com/Sandsy09/create-forge/issues/85),
the last open item in
[CF-EPIC-08](https://github.com/Sandsy09/create-forge/issues/39), is what
finally writes the coverage ADR 0016 deferred.

Verified empirically before writing any test: `--engine-preview` renders a
real project for both `library` and `cli`, and each one's own
`uv run poe check` (ruff format, ruff check, mypy strict, pytest) passes
clean. The engine path runs no `copier.yml` `_tasks` — a rendered project has
no `.git`, no `uv.lock`, no `pre-commit` hook install — so "the generated
project" means something materially different here than it does for the
Copier suite. And unlike the Copier path, the happy path needs **no
network**: the engine is an installed package resolved once at `uv sync`
time, not a template cloned per run.

The issue's second acceptance criterion — prove an unsupported
package/protocol combination makes no final writes, against the *released*
range rather than a development pin — has no published out-of-range version
to install: `0.3.1` is currently the only `forge-template` release on PyPI.
`forge-template`'s git history does carry an earlier tag, `v0.3.0`, genuinely
below the declared lower bound.

## Decision

**A new sibling module, `tests/test_e2e_engine_generation.py`, not an
extension of `test_e2e_generation.py`.** The two paths share almost nothing
beyond the console script they invoke — different answer set, archetype
selection, no `_tasks`, no network on the happy path — so one module trying
to serve both would carry more conditional structure than two focused ones.
The genuinely shared parts (`_create_forge_command`/`_child_env`, this
decision's only mechanical change to the existing suite) move into
`tests/conftest.py` as session-scoped fixtures
(`create_forge_command`/`e2e_child_env`) so both modules use the identical
resolution and leak-free child environment rather than duplicating it.

**Both archetypes, generated once per session, each checked with a full
`uv run poe check`.** Matches CF-08.03's parity theme: `library` and `cli`
are equally production since `forge-template 0.3.0`, and only running one
would leave the other's console-script entry point — the CLI Application
archetype's whole reason for existing — with no end-to-end proof.

**An out-of-range engine installed from forge-template's `v0.3.0` git tag, as
a test fixture only.** This is not a weakening of
[ADR 0018](0018-pypi-distribution-and-the-first-engine-range.md)'s PyPI-only
*declared* dependency — `pyproject.toml`'s `[project.optional-dependencies].engine`
is untouched, and nothing in the normal install or test path resolves this
tag. It exists solely inside one test's own `uv run --isolated --with
<repo-root> --with 'forge-template @ git+...@v0.3.0'` invocation, mirroring
the sibling-checkout pattern `docs/cross-repository-workflow.md` already uses
for local development builds, just pointed at a tagged commit instead of a
working tree. `0.3.0` stays permanently out of bounds as the range moves —
[ADR 0012](0012-engine-dependency-update-policy.md) only ever widens it
upward — so this fixture needs no maintenance when a new compatible release
ships. The assertion reads the boundary from `compat.SUPPORTED_ENGINE_RANGE`
rather than a literal, so it keeps telling the truth if that range changes.

**A second isolated-environment negative test proves the other released-
install boundary: no engine extra at all.** `uv run --isolated --with
<repo-root>` (no `forge-template` `--with`) reaches the same
`ImportError`-guarded branch
([ADR 0014](0014-lazy-engine-reachability.md)) a plain
`pip install create-forge` would. `test_cli.py` already proves this cheaply
with a monkeypatched `builtins.__import__`; this is the same boundary,
exercised for real.

Both negative tests build a package from source inside an isolated
environment, which needs GitHub reachable — they skip, not fail, using the
same `git ls-remote` reachability guard `test_drift.py`,
`test_update_network.py`, and `test_e2e_generation.py` already use. The
happy-path tests carry no such guard.

**CI headroom, not a new job.** `.github/workflows/ci.yml`'s `e2e` job
already runs `uv sync --all-groups --all-extras`, so no dependency-install
step changes. Its `timeout-minutes` moves `20` → `30` for margin; measured
locally, both e2e modules together run in about a minute.

## Consequences

- CF-EPIC-08 closes: CF-08.04 was its last open child issue, and
  [forge-template#4 / FT-08.04](https://github.com/Sandsy09/forge-template/issues/4)
  and [#9](https://github.com/Sandsy09/create-forge/issues/9) — the epic's
  other completion-criteria items — were already resolved.
- The engine path's happy-path coverage is more deterministic than the
  Copier suite's: no template clone, no tag resolution, nothing that can
  drift between runs. Only the two negative tests share the Copier suite's
  network-dependent, skip-on-unreachable character.
- `docs/end-to-end-tests.md`'s "engine-path gap" section is retired; the
  document now describes both tiers as implemented.
- The fast suite's monkeypatched incompatibility tests
  (`test_cli.py`, `test_engine_cross_repository.py`) are not removed or
  superseded — they remain the cheap, always-run guard; this suite is the
  expensive, real-subprocess proof of the same two boundaries.
- A future `forge-template` release that moves
  `compat.SUPPORTED_ENGINE_RANGE`'s lower bound above `0.3.1` does not
  invalidate `v0.3.0` as the out-of-range fixture — it was already below the
  old bound and stays below any bound that only ever increases.
