# End-to-End Tests

This is the living contributor contract for how `create-forge` is tested as
users actually experience it. [ADR 0016](adr/0016-end-to-end-reference-client-tests.md)
records the decision this document keeps current.

## Status

`tests/test_e2e_generation.py` runs the real `create-forge` console script
against `forge-template`'s latest released tag, then the generated project's
own `uv run poe check`. It covers the Copier path only — the engine path has
no `e2e`-tier coverage yet, even though #9 ([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md))
has now assigned it a released, installable range; see
[the engine-path gap](#the-engine-path-gap) below for what changed and what
is still open.

## The three-tier test split

| Tier | Marker | What it owns | Cost |
| --- | --- | --- | --- |
| Fast | *(none)* | Resolved values and in-memory behaviour — `ScaffoldRequest` construction, staging/finalisation bytes, prompt flow, registry validation. No network, no subprocess beyond what a test fakes. | Seconds; runs on every `poe check`. |
| Network | `network` | `forge-template`'s `copier.yml` matches `templates.toml` (the drift guard, invariant 1 in `CLAUDE.md`); a real `update()` between two released tags. Clones a repository or drives Copier's Python API in-process. | Seconds to low tens of seconds. |
| End-to-end | `e2e` | The real console script, its `_tasks`, and the generated project's own checks. | Over a minute — this is dramatically more expensive than `network` and must stay separable from it. |

`poe test` (the fast suite `uv run poe check` runs) excludes both `network`
and `e2e`: `pytest -m 'not network and not e2e'`. `uv run pytest -m network`
and `uv run poe test:e2e` run each tier standalone. `pytest -m network` and
`-m e2e` are equivalent to the poe tasks and useful for a single focused run.

## What the e2e suite proves

A session-scoped fixture scaffolds exactly one real project — every test in
the module asserts against that one result rather than paying for its own
clone:

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

## What it deliberately does not prove

- **Answer-combination coverage.** `forge-template` owns that, via its own
  `poe combos` (see `docs/cross-repository-workflow.md`). One representative
  answer set is in scope here; a matrix here would duplicate a responsibility
  CF-07.06's own issue text assigns elsewhere.
- **Windows.** The e2e CI job runs on `ubuntu-latest` only. The existing
  `windows` CI job covers the fast suite on Windows; running the full e2e
  suite there is a manual step before a PR touching `cli.py`, `runner.py`, or
  `staging.py` — this repository is developed on Windows, so this gap is
  worth closing by hand until it is worth a second CI job.
- **The engine path.** See below.

## The engine-path gap

`--engine-preview` cannot be exercised end-to-end (i.e. in a CI-enforced
`e2e`-marked test) today, but the reason has narrowed twice now. CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) first moved this
repository's development pin to `forge-template==0.3.0`, whose production
catalogue ships both `library` and `cli` — `--engine-preview` generates a
real project, proven at the fast-suite level by
`test_pipeline.py::test_build_generation_request_succeeds_against_the_real_catalogue`
and `test_cli.py::test_new_engine_preview_generates_a_real_cli_application`.
#9 ([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md))
then removed the second blocker: `forge-template` now publishes an
installable, range-assigned `0.3.1` release to PyPI, and `create-forge[engine]`
is an ordinary optional dependency an `e2e`-tier test *could* install, the
same way it installs `forge-template`'s Copier template today.

What remains is writing that coverage: an `e2e`-marked test that installs
`create-forge[engine]`, drives `new --engine-preview` for real, and runs the
generated project's own checks, plus the "unsupported combination makes no
final writes" proof against the released range rather than a development
pin. That work is **CF-08.04**, under
[CF-EPIC-08](https://github.com/Sandsy09/create-forge/issues/39) — now
unblocked, not yet done.

## Running it

```bash
uv run poe test:e2e     # equivalent: uv run pytest -m e2e
```

Skips (does not fail) when GitHub is unreachable, the same way
`test_drift.py` and `test_update_network.py` do. Determinism holds within a
run — the session fixture scaffolds once and every test asserts against that
result — but the suite resolves `forge-template`'s *latest* released tag
rather than a pin, the same deliberate exposure `test_drift.py` accepts: it
tests what a real `uvx create-forge new` gives a user today, and the Monday
cron surfaces template breakage independent of any push to this repository.

## Executable examples

- [`tests/test_e2e_generation.py`](../tests/test_e2e_generation.py) — the
  suite this document describes.
- [`tests/test_cli.py`](../tests/test_cli.py) —
  `test_new_rejects_a_non_empty_destination_before_copier`,
  `test_new_removes_a_destination_it_created_on_failure`, and
  `test_new_leaves_a_pre_existing_destination_untouched_on_failure` prove the
  same conflict/cleanup behaviour at the CLI layer, with only `runner.run_copy`
  faked, for a cost this fast suite can afford on every run.
- [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)'s `e2e` job —
  where this runs in CI, and how it stays separate from `network`.

When end-to-end behaviour or its CI placement changes, update this contract
and its executable examples in the same pull request.
