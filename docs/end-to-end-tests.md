# End-to-End Tests

This is the living contributor contract for how `create-forge` is tested as
users actually experience it. [ADR 0016](adr/0016-end-to-end-reference-client-tests.md)
records the decision this document keeps current.

## Status

Two `e2e`-marked modules cover both generation paths. `tests/test_e2e_generation.py`
runs the real `create-forge` console script against `forge-template`'s latest
released tag, then the generated project's own `uv run poe check` — the
Copier path (CF-07.06, [ADR 0016](adr/0016-end-to-end-reference-client-tests.md)).
`tests/test_e2e_engine_generation.py` does the same for `--engine-preview`,
against the real installed `forge-template>=0.3.1,<0.4` engine — the engine
path (CF-08.04, [ADR 0020](adr/0020-engine-path-end-to-end-tests.md)), which
had no coverage here until this range existed to install
([#9](https://github.com/Sandsy09/create-forge/issues/9),
[ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)).
See [the engine path](#the-engine-path) below for how it differs from the
Copier suite.

## The three-tier test split

| Tier | Marker | What it owns | Cost |
| --- | --- | --- | --- |
| Fast | *(none)* | Resolved values and in-memory behaviour — `ScaffoldRequest` construction, staging/finalisation bytes, prompt flow, registry validation. No network, no subprocess beyond what a test fakes. | Seconds; runs on every `poe check`. |
| Network | `network` | `forge-template`'s `copier.yml` matches `templates.toml` (the drift guard, invariant 1 in `CLAUDE.md`); a real `update()` between two released tags. Clones a repository or drives Copier's Python API in-process. | Seconds to low tens of seconds. |
| End-to-end | `e2e` | The real console script for both generation paths, and each generated project's own checks. | Well under two minutes locally for both modules together — dramatically more expensive than `network` and must stay separable from it, but not the "over a minute per module" cost the Copier suite alone once implied; the engine path's happy tests need no network at all. |

`poe test` (the fast suite `uv run poe check` runs) excludes both `network`
and `e2e`: `pytest -m 'not network and not e2e'`. `uv run pytest -m network`
and `uv run poe test:e2e` run each tier standalone. `pytest -m network` and
`-m e2e` are equivalent to the poe tasks and useful for a single focused run.

## The Copier path

`tests/test_e2e_generation.py`'s session-scoped fixture scaffolds exactly one
real project — every test in the module asserts against that one result
rather than paying for its own clone:

- **The command succeeds** against a real, unmocked destination.
- **The generated tree has the expected shape**, including `.git/` and
  `uv.lock` — proof `copier.yml`'s `_tasks` actually ran, not just Copier's
  own file rendering.
- **The answers round-trip.** `test_drift.py` proves every registry prompt
  key exists in `copier.yml`; this proves the *values* passed on the command
  line land unchanged in `.copier-answers.yml`, catching invariant 1's silent
  failure mode (an unrecognised `data` key vanishes with no error) from the
  user's own side, not just the schema side.
- **The generated project passes its own canonical check** —
  `uv run poe check` inside it, exit `0`.
- **A non-empty destination is refused** by the real binary, with nothing
  written — cheap, since `staging.ensure_available` fails before any clone.

Deliberately not proven here: **answer-combination coverage**
(`forge-template` owns that via its own `poe combos` — see
`docs/cross-repository-workflow.md`; one representative answer set is in
scope, a matrix would duplicate a responsibility CF-07.06's own issue text
assigns elsewhere) and **Windows** (the e2e CI job runs on `ubuntu-latest`
only; the existing `windows` CI job covers the fast suite on Windows, and
running the full e2e suite there is a manual step before a PR touching
`cli.py`, `runner.py`, or `staging.py`).

## The engine path

`tests/test_e2e_engine_generation.py` covers `--engine-preview` against the
real installed `forge-template>=0.3.1,<0.4` engine (CF-08.04,
[ADR 0020](adr/0020-engine-path-end-to-end-tests.md)). It differs from the
Copier suite in ways worth being explicit about:

- **No `_tasks` run.** The engine path has no equivalent of `copier.yml`'s
  post-generation hooks — a rendered project has no `.git`, no `uv.lock`, no
  `pre-commit` install. `uv run poe check` inside it builds that project's
  own environment from a cold start. The suite asserts this absence
  explicitly rather than leaving it implicit.
- **The happy path needs no network.** `forge-template` is an installed
  package resolved once when `uv sync --all-extras` runs, not a template
  cloned per test session — generating through it is as deterministic as any
  other in-process call.
- **Both archetypes are covered**, each with a full `uv run poe check`:
  `library` and `cli` are equally production since `forge-template 0.3.0`,
  and the suite proves `cli`'s console-script entry point derives from
  `ProjectSpec.project.repository_name` — the end-to-end counterpart to
  CF-08.03's in-memory proof
  ([ADR 0019](adr/0019-cli-archetype-parity-review.md)).
- **The "unsupported combination" proof uses two real isolated installs, not
  a monkeypatched `EngineInfo`.** One installs `forge-template` from git tag
  `v0.3.0` — a real release genuinely below
  `compat.SUPPORTED_ENGINE_RANGE`'s lower bound, since `0.3.1` is currently
  the only PyPI release — and asserts exit status `3` with nothing written.
  The other installs `create-forge` with no `engine` extra at all and asserts
  exit status `1` with nothing written. Both need GitHub reachable to build
  the isolated environment, so both skip (not fail) when it is not.

## Running it

```bash
uv run poe test:e2e     # equivalent: uv run pytest -m e2e
```

`tests/test_e2e_engine_generation.py` skips itself entirely when the
`engine` extra is not installed (`uv sync` without `--all-extras`); its two
negative tests, and the whole of `tests/test_e2e_generation.py`, skip (do not
fail) when GitHub is unreachable, the same way `test_drift.py` and
`test_update_network.py` do. Determinism holds within a run for every session
fixture, but the Copier suite resolves `forge-template`'s *latest* released
tag rather than a pin, the same deliberate exposure `test_drift.py` accepts:
it tests what a real `uvx create-forge new` gives a user today, and the
Monday cron surfaces template breakage independent of any push to this
repository.

## Executable examples

- [`tests/test_e2e_generation.py`](../tests/test_e2e_generation.py) — the
  Copier-path suite.
- [`tests/test_e2e_engine_generation.py`](../tests/test_e2e_engine_generation.py) —
  the engine-path suite.
- [`tests/conftest.py`](../tests/conftest.py) — the `create_forge_command`
  and `e2e_child_env` fixtures both suites share.
- [`tests/test_cli.py`](../tests/test_cli.py) —
  `test_new_rejects_a_non_empty_destination_before_copier`,
  `test_new_removes_a_destination_it_created_on_failure`, and
  `test_new_leaves_a_pre_existing_destination_untouched_on_failure` prove the
  same conflict/cleanup behaviour at the CLI layer, with only `runner.run_copy`
  faked, for a cost this fast suite can afford on every run;
  `test_new_engine_preview_exits_3_on_incompatible_engine` and
  `test_new_engine_preview_fails_cleanly_without_the_engine_dependency` prove
  the engine path's equivalent boundaries the same cheap way.
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)'s `e2e` job —
  where both suites run in CI, and how the job stays separate from `network`.

When end-to-end behaviour or its CI placement changes, update this contract
and its executable examples in the same pull request.
