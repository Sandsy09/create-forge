# 16. Test the reference client end to end against the released template

## Status

Accepted

## Context

[CF-07.06](https://github.com/Sandsy09/create-forge/issues/51) is the last
open child of [CF-EPIC-07](https://github.com/Sandsy09/create-forge/issues/38).
Every other suite in this repository proves a resolved value: `test_cli.py`
asserts the `ScaffoldRequest` a command would issue, `test_staging.py` and
`test_pipeline.py` assert bytes written to a directory, `test_drift.py`
asserts a registry key exists in `forge-template`'s `copier.yml`. None of
them ever run the actual `create-forge` console script users get from `uvx
create-forge`, or check the project it produces. `docs/cross-repository-workflow.md`
names exactly that gap as a *manual* verification step. CF-07.06 automates
it — and it is also the one test that can catch invariant 1's silent failure
mode from the user's side: Copier drops an unrecognised `data` key with no
error, so a scaffold can exit `0` and still be wrong. `test_drift.py` proves
the keys line up with `copier.yml`; nothing before this proved the *values*
survive the round trip into a real `.copier-answers.yml`.

The issue's text asks for more than that, though: generate through the
*public engine*, against a "known compatible **released** engine-and-assets
unit". Neither exists at the time of this record. `forge-template` publishes
no `0.2.x` release — the runtime dependency range stays unassigned until
[#9](https://github.com/Sandsy09/create-forge/issues/9) — and its production
catalogue is intentionally empty until
[FT-08.02 / forge-template#41](https://github.com/Sandsy09/forge-template/issues/41).
`--engine-preview` therefore fails deterministically at `validate()` today,
proven already by `test_pipeline.py` and `test_cli.py`'s
`test_new_engine_preview_fails_closed_against_the_empty_catalogue`. There is
nothing for an end-to-end engine test to generate yet.

## Decision

**Automate the reachable half now; carry the rest to a successor issue.**
CF-07.06 closes with five of its seven acceptance criteria met by real,
executable coverage. The two criteria that require a released engine and a
non-empty catalogue move verbatim to **CF-08.04**, filed under
[CF-EPIC-08](https://github.com/Sandsy09/create-forge/issues/39) and blocked
on the same two things that block them here.

**A new `e2e` test, distinct from `network`.** `tests/test_e2e_generation.py`
carries only `@pytest.mark.e2e`, never `network`. The two are already
different in kind — `network` (`test_drift.py`, `test_update_network.py`)
clones a repository and inspects it or runs Copier's Python API in-process,
finishing in seconds; `e2e` runs the real console script, which itself runs
`copier.yml`'s `_tasks` (`git init`, `uv sync --all-groups`,
`uv run pre-commit install --install-hooks`) and then the generated
project's own `uv run poe check`, taking well over a minute. Reusing
`network` would force the drift guard to pay that cost on every run; a
distinct marker and CI job (`e2e`, gating PRs and joining `all-green`,
alongside the existing Monday cron) keeps them separable, per the issue's
own *"keep local fast tests isolated from released cross-repository
end-to-end paths"* scope line — `poe test`'s `-m 'not network and not e2e'`
excludes both from the fast suite the same way.

**The real console script, invoked as a subprocess — not `CliRunner`.**
Typer's `CliRunner` (used everywhere else in `test_cli.py`) calls `app`
in-process; it never exercises the `[project.scripts]` entry point itself,
its console encoding, or its process boundary. A subprocess does, and gets
two things for free that an in-process call cannot. First, git identity:
`_tasks` shells out to `git commit`, and `subprocess.run(..., env=...)`
supplies `GIT_AUTHOR_*`/`GIT_COMMITTER_*` to the whole child process tree
directly — contrast `test_update_network.py`'s
`_git_identity_for_template_tasks` fixture, which has to mutate
`plumbum.local.env` in-place because plumbum snapshots `os.environ` at
import and an in-process `monkeypatch.setenv` never reaches it. Second,
environment isolation: `_tasks`' `uv sync --all-groups` must resolve *the
generated project's* environment, not this repository's own — `VIRTUAL_ENV`,
`UV_PROJECT_ENVIRONMENT`, `PYTHONHOME`, and `PYTHONPATH`, all set by
`uv run` for the outer pytest process, are stripped from the child's `env`
so they cannot leak into the inner `uv sync`.

**One representative answer set, not a combination matrix.** `forge-template`
already owns combination coverage of its own question space
(`docs/cross-repository-workflow.md`'s `poe combos` row); duplicating it here
would violate the "no implementation concern duplicated across repositories"
rule CF-07.06's own Repository Ownership section states. The template's
canonical `uv run poe check` — `ruff format --check`, `ruff check`, `mypy`,
`pytest` — runs against that one project, on `ubuntu-latest` only; a Windows
e2e job is left to manual verification, the same boundary the existing
`windows` CI job already draws for the fast suite alone.

**The registry's URL at its latest resolved tag, not a pin.** This mirrors
`test_drift.py` and `test_update_network.py`: it tests what `uvx create-forge
new` actually resolves for a user today, skips (does not fail) when GitHub is
unreachable, and lets the Monday cron surface template breakage independent
of any push here.

## Consequences

- CF-EPIC-07 closes: all three children are complete and its
  *"a real `new` path and generated-project checks run in CI"* completion
  criterion is now genuinely met, on the Copier path.
- A regression in `cli.py`, `runner.py`, or `staging.py` that breaks a real
  scaffold or the generated project's own checks is now caught by CI before
  merge, not discovered by a user.
- The engine path stays completely uncovered end-to-end. `--engine-preview`
  remains provably dead-ended at validation (unit-tested), but no test has
  ever produced a project through it, because none can yet. This is a known,
  named gap — CF-08.04 — not a silent one.
- The generated project's own dependencies float at their own lower bounds
  (e.g. `ruff>=0.14`, `mypy>=1.14`); a new release of either can fail this
  suite with nothing changed in either repository. That risk already exists
  for `forge-template`'s own CI and is accepted here rather than pinned
  around, for the same reason `test_drift.py`'s Monday cron exists: it is a
  signal worth surfacing, not a false alarm to suppress.
- The e2e job's cost (minutes, not seconds) is paid on every pull request
  touching this repository, not only on template changes — accepted because
  the alternative (post-merge only) lets a regression land on `main` first.
