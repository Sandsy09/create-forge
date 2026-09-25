# Contributing

Thanks for considering a contribution. This covers the human workflow — set
up, make a change, validate it, open a PR, release. For the rules that keep
`create-forge` correct — module boundaries, why `unsafe=True` is load-bearing,
and so on — see [CLAUDE.md](CLAUDE.md); this file won't restate them.

## Getting set up

```bash
uv sync --all-groups --all-extras
uv run pre-commit install --install-hooks
```

`forge-template` and `uv` are required dependencies — a plain `uv sync` (no
extras) resolves them, same as `pip install create-forge`. `--all-extras` also
resolves `copier` and `platformdirs`, the optional `legacy` extra. Omit
`--all-extras` if your change doesn't touch `--legacy`, `update`, or
`runner.py`.

## Making a change

1. Open or pick an issue describing the change.
2. If it changes an architecture boundary, dependency range, or CLI surface,
   it needs an ADR — see "Architecture decisions" below.
3. If a canonical contract in [docs/README.md](docs/README.md) describes the
   behaviour you're changing, update it in the same PR.
4. Implement, matching the surrounding code's style.
5. Run the checks below, then open a PR.

## Running the tests

Three tiers, run at different points:

**Fast suite** — every commit, matrixed in CI across Python 3.11–3.14:

```bash
uv run poe check
```

Runs `ruff format --check`, `ruff check`, `mypy`, and
`pytest -m 'not network and not e2e'`.

**Network-marked tests** — run when `templates.toml` changes, or whenever
`forge-template` cuts a new tag:

```bash
uv run pytest -m network
```

This hits GitHub: `tests/test_drift.py` clones `forge-template` and checks
every prompt key in `templates.toml` still matches a question in its
`copier.yml` (a mismatch fails *silently* otherwise — Copier drops an unknown
`data` key with no error, the template's own default applies, and the
scaffold looks fine but is subtly wrong); `tests/test_update_network.py` runs
a real end-to-end `create-forge update` against `forge-template`'s actual
tags.

**End-to-end tests** — slow; run when touching generation, the engine
boundary, or before a release:

```bash
uv run poe test:e2e
```

Runs the real `create-forge` console script through the Copier and engine
paths and each generated project's own checks, plus installed-candidate and
rollout-regression coverage. See the canonical
[end-to-end tests contract](docs/end-to-end-tests.md).

Before any release, also run:

```bash
uv run poe check:wheel
```

Editable installs read `templates.toml` from source; a built wheel does not
unless Hatchling's package-data rules are still correct. This is the one
check that catches a missing registry ahead of a user's first `uvx` run.

## Opening a pull request

Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, ...) — a
`commit-msg` hook enforces this once `pre-commit install --install-hooks` has
run. Fill in the PR template's "what and why", confirm `uv run poe check`
passes, and run `pytest -m network` if `templates.toml` changed. Wait for
`All checks passed` before merging; squash-merge is the norm here.

## What CI runs

`.github/workflows/ci.yml` runs on every push to `main` and every pull
request. Its Linux jobs (everything except `windows`, `e2e-windows*` and
`all-green`) are defined once in `.github/workflows/linux-checks.yml` and called
on the pinned `ubuntu-24.04` baseline, so their names appear as
`Linux (ubuntu-24.04) / <job>`. No workflow uses `ubuntu-latest`; see
[docs/ci-runner-baseline.md](docs/ci-runner-baseline.md).

| Job | What |
| --- | --- |
| `lint` | `pre-commit run --all-files`, then `mypy` — the exact gate that runs locally on commit |
| `test` | the fast suite, matrixed across Python 3.11–3.14 — includes `tests/test_workflows.py`, the SHA-pin and permission-placement guard for `.github/workflows/` |
| `windows` | the fast suite on `windows-latest` — this tool is developed on Windows |
| `wheel` | `poe check:wheel` |
| `floor` | the fast suite with `uv --resolution lowest-direct`, so declared lower bounds are exercised, not just whatever CI resolves (see "Dependency floors" below) |
| `network` | `pytest -m network` — the `copier.yml` drift guard, plus the real `update()` end-to-end. Per [ADR 0012](docs/adr/0012-engine-dependency-update-policy.md), this is the proof a compatibility-line dependency bump (e.g. Copier) requires before `all-green` allows the merge |
| `e2e` | `pytest -m e2e` — both generation paths, installed-candidate Data Science and rollout regression, real destinations, and generated-project checks ([end-to-end contract](docs/end-to-end-tests.md)) |
| `all-green` | an aggregate check; this is the one branch protection requires. It gates the pinned Linux call and the Windows jobs, and never the canary |
| `Runner canary` | `runner-canary.yml`: the identical Linux jobs on the *next* Ubuntu image (`ubuntu-26.04`). **Not required and not part of `all-green`** — a red canary is triaged, not a blocked merge. Ownership and promotion criteria: [docs/ci-runner-baseline.md](docs/ci-runner-baseline.md) |

`network` and `e2e` also run on a Monday cron, independent of any push here —
`forge-template` moves on its own schedule, so a PR is not the only thing that
can surface a registry mismatch or a template regression.

## Working across both repositories

A change that coordinates this CLI with a local `forge-template` checkout
follows the canonical
[cross-repository contributor workflow](docs/cross-repository-workflow.md):
sibling-checkout commands, the local registry/schema drift check, the trust
boundary, the validation ladder, and the safe merge/release order.

## Documentation

The shared [Forge site](https://sandsy09.github.io/create-forge/) is authored
in [docs/user-guide/](docs/user-guide/) — end-user walkthroughs and
troubleshooting. Everything else in `docs/` is a contract document, indexed at
[docs/README.md](docs/README.md).

```bash
uv sync --locked
uv run poe docs         # preview at http://127.0.0.1:8000/create-forge/
uv run poe docs:build   # strict build, writes site/
```

When changing user-visible behaviour, update the affected guides and README
examples in the same PR. CI builds the site on every PR; `main` deploys it
automatically. Pre-commit lints the root README and user-guide Markdown.

## Architecture decisions

Significant decisions live in [docs/adr/](docs/adr/) as Architecture Decision
Records (Nygard format: `## Status`, `## Context`, `## Decision`,
`## Consequences`). Add one by copying the most recent record and
incrementing the number; records are immutable, so a decision that changes is
superseded by a new record, not an edit to an old one.

```bash
uv run poe check:adr    # numbering, index entry, headings
```

`poe test` runs this and `check:workflows` too. Every canonical contract this
authorises should be linked from [docs/README.md](docs/README.md) in the same
PR.

## Workflow security

Every external action in `.github/workflows/` is pinned to a full commit SHA;
workflow-level `permissions:` is read-only with `write`/`id-token` scopes only
on the jobs that need them. `scripts/check_workflows.py`
(`uv run poe check:workflows`) enforces both. When Dependabot proposes an
Action bump, confirm the SHA before approving. This repo is set to
**Allow select actions**, so a brand-new third-party action also needs an
allowlist entry in the same change. Full rules:
[workflow security contract](docs/workflow-security.md),
[ADR 0037](docs/adr/0037-immutable-workflow-actions.md).

## Dependency floors

Declared lower bounds (e.g. `copier>=9.16`) are a support claim the CI `floor`
job proves. They move only on advisory or required-behaviour evidence, never
because Dependabot bumped the lock. Before a release, re-check the `copier`
floor against published advisories:

```bash
gh api graphql -f query='{ securityVulnerabilities(first: 20, ecosystem: PIP, package: "copier") { nodes { advisory { ghsaId severity } vulnerableVersionRange firstPatchedVersion { identifier } } } }'
```

A new advisory below the floor means raising it — with a new ADR and a patch
release — before other release content. See
[ADR 0038](docs/adr/0038-dependency-floor-review.md) and
[docs/engine-updates.md](docs/engine-updates.md).

## Labels

[.github/labels.toml](.github/labels.toml) is the source of truth for this
repo's issue and PR labels, shared with `forge-template`. Apply it with:

```bash
uv run poe labels:sync --dry-run   # preview, changes nothing
uv run poe labels:sync --prune     # apply, deleting extras
```

## Releasing

`pyproject.toml`'s `version` is the single source of truth for a release's
tag — see [ADR 0009](docs/adr/0009-pyproject-as-the-single-version-source.md).

0. **Confirm the installed safety evidence still applies.** Update safety is
   proven through the installed wheel, and `main` goes red if the code that
   evidence covers changes without it being refreshed. Before the bump PR, run
   `uv run poe evidence:candidate` on the commit you will release and follow the
   release-prerequisite checklist in
   [docs/update-safety-validation.md](docs/update-safety-validation.md): it also
   records the exact artefact hashes for both installed suites (update safety
   and Streamlit) that the release needs. If the guard test fails, re-run
   `uv run pytest tests/test_e2e_installed_update_safety.py` and refresh the
   record first.
1. Open a PR bumping `pyproject.toml`'s `version` and regenerating the
   changelog: `uv run git-cliff --tag vX.Y.Z --output CHANGELOG.md`.
2. Merge it. Wait for `All checks passed` on `main`.
3. Actions → Release → Run workflow, with `dry_run` checked. Confirm the
   computed tag and generated notes in the run summary.
4. Run it again with `dry_run` unchecked. This tags `main`, pushes the tag,
   publishes the GitHub release, and publishes `create-forge` to PyPI via
   Trusted Publishing (OIDC; no stored token, gated by the `pypi` GitHub
   Environment). `forge-template` releases the same way on its own repository
   and schedule.
