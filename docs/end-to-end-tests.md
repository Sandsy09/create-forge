# End-to-End Tests

This is the living contributor contract for how `create-forge` is tested as
users actually experience it. [ADR 0016](adr/0016-end-to-end-reference-client-tests.md)
records the decision this document keeps current.

## Status

Four `e2e`-marked modules cover both generation paths, the installed
Data Science release-candidate boundary, and the installed rollout regression
matrix. `tests/test_e2e_generation.py`
runs the real `create-forge` console script against `forge-template`'s latest
released tag, then the generated project's own `uv run poe check` — the
Copier path (CF-07.06, [ADR 0016](adr/0016-end-to-end-reference-client-tests.md)).
`tests/test_e2e_engine_generation.py` does the same for `--engine-preview`,
against the real installed `forge-template>=0.4.1,<0.5` engine — the engine
path (CF-08.04, [ADR 0020](adr/0020-engine-path-end-to-end-tests.md)), with
client-owned lock finalisation from
[ADR 0021](adr/0021-client-finalises-engine-lockfiles.md), which
had no coverage here until this range existed to install
([#9](https://github.com/Sandsy09/create-forge/issues/9),
[ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)). It
covers every archetype the catalogue discovers; CF-13.05
([ADR 0030](adr/0030-data-science-preview-pipeline-validation.md)) added the
Data Science composition — `data-science` with its `jupyter` and
`scientific-python` capabilities — alongside `library` and `cli`.
CF-14.02 ([ADR 0032](adr/0032-validate-installed-data-science-generation.md))
adds `tests/test_e2e_installed_data_science.py`: it builds and installs the
create-forge `0.3.0` candidate wheel with the published `forge-template 0.4.1`
engine, then validates both accepted Data Science compositions. CF-14.03
([ADR 0033](adr/0033-complete-rollout-regression-validation.md)) adds
`tests/test_e2e_installed_rollout.py`, which reuses that wheel for everything
CF-14.02 left out: the Library and CLI Application engine paths, the default
Copier path in a wheel with no engine installed, a real out-of-range engine,
and the full selection / option / destination / lock / cleanup failure matrix.
See [the engine path](#the-engine-path),
[the installed Data Science path](#the-installed-data-science-path), and
[the installed rollout path](#the-installed-rollout-path) below.

## The three-tier test split

| Tier | Marker | What it owns | Cost |
| --- | --- | --- | --- |
| Fast | *(none)* | Resolved values and in-memory behaviour — `ScaffoldRequest` construction, staging/finalisation bytes, prompt flow, registry validation. No network, no subprocess beyond what a test fakes. | Seconds; runs on every `poe check`. |
| Network | `network` | `forge-template`'s `copier.yml` matches `templates.toml` (the drift guard, invariant 1 in `CLAUDE.md`); a real `update()` between two released tags. Clones a repository or drives Copier's Python API in-process. | Seconds to low tens of seconds. |
| End-to-end | `e2e` | The real console script for both generation paths, installed-candidate Data Science validation, and each generated project's own checks. | Minutes rather than seconds. The existing engine suite's happy path needs no network; the installed-candidate suite resolves the reviewed engine from PyPI, restores scientific-Python and Jupyter dependency trees, and executes live notebooks across the Python handoff matrix; CF-14.03's rollout suite adds three more installed environments and an engine-less Copier generation on top. The CI job's budget is 60 minutes. |

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
real installed `forge-template>=0.4.1,<0.5` engine (CF-08.04,
[ADR 0020](adr/0020-engine-path-end-to-end-tests.md); range moved by
[ADR 0026](adr/0026-adopt-the-0-4-engine-compatibility-line.md), reviewed
release adopted by
[ADR 0031](adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md)). It differs
from the Copier suite in ways worth being explicit about:

- **No `_tasks` run.** The engine path creates `uv.lock` as a client
  finalisation artefact before the atomic rename, then proves it with
  `uv lock --check` and `uv run --locked poe check`. It still creates no
  `.git`, `.venv`, hooks, or pre-commit installation. The suite asserts those
  boundaries explicitly rather than leaving them implicit.
- **The happy path needs no network.** `forge-template` is an installed
  package resolved once when `uv sync --all-extras` runs, not a template
  cloned per test session — generating through it is as deterministic as any
  other in-process call.
- **Every discovered archetype is covered**, each with a current lock and a
  full `uv run --locked poe check`, parametrised over an `_ARCHETYPES` module
  constant. `library` and `cli` are equally production since
  `forge-template 0.3.0`, and the suite proves `cli`'s console-script entry
  point derives from `ProjectSpec.project.repository_name` — the end-to-end
  counterpart to CF-08.03's in-memory proof
  ([ADR 0019](adr/0019-cli-archetype-parity-review.md)). CF-13.05
  ([ADR 0030](adr/0030-data-science-preview-pipeline-validation.md)) added
  `data-science`, generated with its `jupyter` and `scientific-python`
  capabilities (an `_EXTRA_ARGS` entry supplies the flags), so its own
  `notebook:check` runs as part of the generated project's `poe check`. The
  fast-suite composition proofs live in
  [`tests/test_data_science_pipeline.py`](../tests/test_data_science_pipeline.py)
  and are mapped to the epic acceptance checklist by the canonical
  [Data Science preview-pipeline validation](data-science-preview-validation.md)
  record.
- **The "unsupported combination" proof uses two real isolated installs, not
  a monkeypatched `EngineInfo`.** One installs `forge-template` from git tag
  `v0.3.0` — a real release genuinely below
  `compat.SUPPORTED_ENGINE_RANGE`'s lower bound, and one that stays out of
  bounds however far that bound is raised ([ADR 0020](adr/0020-engine-path-end-to-end-tests.md)
  pre-authorised this; ADR 0026's move to `>=0.4,<0.5` is the first time it
  applied) — and asserts exit status `3` with nothing written. The other
  installs `create-forge` with no `engine` extra at all and asserts exit
  status `1` with nothing written. Both need GitHub reachable to build the
  isolated environment, so both skip (not fail) when it is not.

## The installed Data Science path

`tests/test_e2e_installed_data_science.py` closes the installed-distribution
gap left deliberately by CF-13.05 and the provider's release audit. It builds
a fresh create-forge `0.3.0` wheel, installs `wheel[engine]` plus exactly the
published `forge-template 0.4.1` into a temporary Python 3.13 environment, and
uses that environment's console script and `uv` executable throughout.

Both accepted Data Science compositions generate twice. Every rendered file
is matched byte-for-byte to the installed pipeline's Foundation/component
ownership plan, every selected component contributes, and the two complete
trees — including client-owned `uv.lock` — are byte-identical. Each project
then restores from the lock, passes its own canonical check and explicit
notebook execution, builds a wheel and sdist with no ignored working-tree
payload, and installs independently with neither Forge distribution present.
The full Scientific Python composition also runs its generated smoke test and
repeats the locked check/notebook path at Python 3.11 and 3.14.

The canonical
[installed Data Science validation](installed-data-science-validation.md)
record maps every #112 acceptance criterion to a named test. This suite does
not replace or broaden the existing Library, CLI Application, Copier, or
failure-path suites — [the installed rollout path](#the-installed-rollout-path)
below covers those at the same boundary.

## The installed rollout path

`tests/test_e2e_installed_rollout.py` (CF-14.03,
[ADR 0033](adr/0033-complete-rollout-regression-validation.md)) closes the
regression and failure matrix CF-14.02 deliberately deferred. It reuses
`tests/conftest.py`'s session `candidate_wheel` — one `uv build` shared with
the Data Science suite — and installs it three ways: with the `engine` extra
and `forge-template 0.4.1`, with no engine at all, and with a real
`forge-template 0.3.2` from PyPI that sits permanently below
`compat.SUPPORTED_ENGINE_RANGE`.

- **Library and CLI Application generate through the installed engine console**
  — project shape, a current lock, every rendered byte matched to the
  installed pipeline's own Foundation/component ownership plan, no Forge
  distribution anywhere, the `cli` console-script name, and
  `uv run --locked poe check`.
- **The default Copier path runs from a wheel with no engine installed** — one
  real generation with `_tasks`, `.copier-answers.yml` round-tripping every
  answer, `.git` and `uv.lock`, and `uv run poe check`. `--version`, `list`
  (proving the bundled `templates.toml` shipped), `doctor --json`, and
  `new --engine-preview`'s actionable rejection are checked in the same
  environment.
- **The compatibility boundary uses the real out-of-range install** —
  `new --engine-preview` exits `3` naming both `0.3.2` and the supported
  range, with nothing written; `doctor --json` reports the out-of-range
  package.
- **The failure matrix runs through the installed console**, parametrised:
  every documented exit status (`docs/cli-conventions.md`'s table), an
  actionable message, the destination absent or byte-identical, and no
  surviving `.create-forge-*` staging sibling. One case exercises a real
  emptied-`PATH` lock failure — `staging.staged()`'s cleanup for real, not a
  faked `create_uv_lock`.

The canonical
[rollout regression and failure validation](rollout-regression-validation.md)
record maps every #113 acceptance criterion, and the epic criteria it
discharges, to a named test.

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

The installed Data Science and rollout suites do not import the engine from the
parent test environment and do not skip an unavailable published package:
resolving the reviewed PyPI release (and, for the rollout suite, the
deliberately out-of-range `forge-template 0.3.2`) is part of the proof. All of
their candidate builds, environments, projects, and artefacts live in
context-managed temporary roots that clean up for both successful and failing
tests. The rollout suite's engine-less Copier generation still needs GitHub, so
it skips rather than fails when GitHub is unreachable.

## Executable examples

- [`tests/test_e2e_generation.py`](../tests/test_e2e_generation.py) — the
  Copier-path suite.
- [`tests/test_e2e_engine_generation.py`](../tests/test_e2e_engine_generation.py) —
  the engine-path suite, parametrised over every discovered archetype.
- [`tests/test_e2e_installed_data_science.py`](../tests/test_e2e_installed_data_science.py) —
  CF-14.02's candidate-wheel suite for both accepted Data Science compositions,
  deterministic locks, the Python handoff matrix, built artefacts, and
  Forge-free isolated installs.
- [`tests/test_e2e_installed_rollout.py`](../tests/test_e2e_installed_rollout.py) —
  CF-14.03's candidate-wheel suite for the Library / CLI Application engine
  paths, the engine-less default Copier path, the real out-of-range engine,
  and the parametrised selection / option / destination / lock / cleanup
  failure matrix.
- [`tests/installed_client.py`](../tests/installed_client.py) — the shared
  harness: the wheel build, the `build_client` environment context manager,
  and the installed-pipeline ownership probe both installed suites use.
- [`tests/test_data_science_pipeline.py`](../tests/test_data_science_pipeline.py) —
  CF-13.05's fast-suite composition proofs against the real installed engine:
  component-owner attribution, the optional-capability render differential,
  the `spec.components` round-trip, staging/lock/finalisation, five
  no-partial-project failure cases, dry-run, and interactive
  required-capability pre-locking.
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
