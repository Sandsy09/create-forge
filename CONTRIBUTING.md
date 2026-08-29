# Contributing

This describes the human workflow — how to set up, validate, and release a
change. For the rules that keep `create-forge` correct — how the registry
relates to `forge-template`'s `copier.yml`, why `unsafe=True` is load-bearing,
and so on — see [CLAUDE.md](CLAUDE.md); this file won't restate them.

## Setup

```bash
uv sync --all-groups
uv run pre-commit install --install-hooks
```

`uv sync` clones `forge-template==0.2.0` at a full pinned commit as part of the
`engine`
dependency group (`[tool.uv] default-groups = ["dev"]` includes it). This is
a development-only dependency for `src/create_forge/engine.py` — see
[ADR 0013](docs/adr/0013-projectspec-construction-boundary.md) — not a
runtime dependency of the released CLI.

## Before opening a pull request

```bash
uv run poe check
```

Runs `ruff format --check`, `ruff check`, `mypy`, and the fast test suite —
`pytest -m 'not network and not e2e'`.

The network-marked tests are separate:

```bash
uv run pytest -m network
```

This hits GitHub and includes two things: `tests/test_drift.py`, which clones
`forge-template` and checks every prompt key in `templates.toml` still matches
a question in its `copier.yml`; and `tests/test_update_network.py`, a real
end-to-end `create-forge update` against `forge-template`'s actual tags.

The drift check exists because a mismatch fails *silently* — Copier drops an
unknown `data` key with no error, the answer vanishes, and the template's own
default applies instead. A typo here produces a scaffold that looks fine and
is subtly wrong, which is exactly the failure mode this test is for. Run it
whenever `templates.toml` changes, or whenever `forge-template` cuts a new tag.

## End-to-end tests

A third tier, separate from both the fast suite and `network`:

```bash
uv run poe test:e2e
```

This runs the real `create-forge` console script against `forge-template`'s
latest released tag, then the generated project's own `uv run poe check`.
It is dramatically slower than `network` — well over a minute, since it runs
`copier.yml`'s `_tasks` (`git init`, `uv sync --all-groups`,
`pre-commit install --install-hooks`) and then a full check on the result —
so it carries its own `e2e` marker and CI job rather than joining `network`.
Like the network-marked tests, it skips rather than fails when GitHub is
unreachable. See the canonical [end-to-end tests contract](docs/end-to-end-tests.md)
and [ADR 0016](docs/adr/0016-end-to-end-reference-client-tests.md).

Before any release, also run:

```bash
uv run poe check:wheel
```

Editable installs read `templates.toml` from source; a built wheel does not
unless Hatchling's package-data rules are still correct. A missing registry
passes every test above and only breaks on a user's first `uvx` run — this is
the one check that catches it ahead of time.

## Cross-repository changes

Changes that coordinate this CLI with a local `forge-template` checkout follow
the canonical [cross-repository contributor workflow](docs/cross-repository-workflow.md).
It defines the sibling-checkout commands, local registry/schema drift check,
trust boundary, validation ladder, and safe merge/release order.

## What CI runs

`.github/workflows/ci.yml` runs on every push to `main` and every pull
request:

| Job | What |
| --- | --- |
| `lint` | `pre-commit run --all-files`, then `mypy` — the exact gate that runs locally on commit |
| `test` | the fast suite, matrixed across Python 3.11–3.14 |
| `windows` | the fast suite on `windows-latest` — this tool is developed on Windows |
| `wheel` | `poe check:wheel` |
| `network` | `pytest -m network` — the `copier.yml` drift guard, plus the real `update()` end-to-end. Per [ADR 0012](docs/adr/0012-engine-dependency-update-policy.md), this is the proof a compatibility-line dependency bump (e.g. Copier) requires before `all-green` allows the merge |
| `e2e` | `pytest -m e2e` — the real console script against a real destination, and the generated project's own `uv run poe check` ([ADR 0016](docs/adr/0016-end-to-end-reference-client-tests.md)) |
| `all-green` | an aggregate check; this is the one branch protection requires |

`network` and `e2e` also run on a Monday cron, independent of any push here —
`forge-template` moves on its own schedule, so a PR is not the only thing that
can surface a registry mismatch or a template regression.

## Architecture decisions

Significant decisions live in [docs/adr/](docs/adr/) as Architecture Decision
Records — why Copier over Cookiecutter, why the two-repo split, why
`unsafe=True` is safe here, and so on. Add one by copying the most recent
record and incrementing the number; records are immutable, so a decision that
changes is superseded by a new record, not an edit to an old one. `poe test`
(and standalone, `uv run poe check:adr`) checks the set stays internally
consistent — filenames, numbering, the index, and the four required headings.

The accepted future boundary with `forge-template` is recorded in
[ADR 0010](docs/adr/0010-public-engine-integration-contract.md), while the
evolving package/protocol rules live in the
[integration contract](docs/integration-contract.md). The canonical
[ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
is defined by `forge-template`; this repository will construct it only through
the [supported engine facade](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md).
That API begins its compatibility contract at `forge-template` `0.2.x`.
Its canonical
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md)
checks rendered output in memory before the facade returns it. Filesystem
staging, finalisation, and command execution remain `create-forge`
responsibilities at the future cutover — the living
[filesystem generation contract](docs/filesystem-generation.md) records how
`staging.py` already implements the staging and finalisation half of that
today, behind `--engine-preview`.
The canonical
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
defines the production `library` component and the manifest/option/planning
migration FT-08.02 must implement. This repository keeps its exact `0.2.0`
development pair, empty-catalogue expectation, and unassigned released engine
range until that migration and the coordinated cutover are implemented and
tested.
Stage 06 proves an exact `0.2.0`/protocol-1 development pair through the
[cross-repository engine contract tests](docs/engine-contract-tests.md), but
this repository assigns no released dependency range until #9 resolves the
distribution channel and a future cutover issue performs the atomic cutover.
CF-07.04 ([ADR 0015](docs/adr/0015-staged-filesystem-generation.md)) moved
the development pin forward once, within that same unreleased `0.2.0`
contract, to adopt generated-project validation.
[ADR 0013](docs/adr/0013-projectspec-construction-boundary.md)
and the living [ProjectSpec construction contract](docs/project-spec-construction.md)
record that adapter's shape — `spec.py` builds the wire payload, `engine.py`
is the one module that calls the facade. The canonical
[component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
likewise remains engine-owned discovery metadata rather than a schema this
repository recreates. The living
[component discovery contract](docs/component-discovery.md) records how
`engine.py` checks both protocol axes before returning those public descriptors
unchanged. [ADR 0014](docs/adr/0014-lazy-engine-reachability.md) adds
`pipeline.py` and reaches this boundary from a real command for the first
time, via the hidden `new --engine-preview` flag and a lazily-imported
module `cli.py` otherwise never touches; ADR 0015 completes that flag with
real staging and finalisation. The default `new` path, and every other
command, remain the current v0.1.x Copier/registry implementation,
authoritative until the coordinated CLI cutover.
[ADR 0016](docs/adr/0016-end-to-end-reference-client-tests.md) and the living
[end-to-end tests contract](docs/end-to-end-tests.md) close Stage 07 with
real, CI-enforced coverage of that default `new` path against a released
template — the engine path stays untested end to end until it has a released
version and a non-empty catalogue to generate from, tracked as CF-08.04.
[ADR 0011](docs/adr/0011-engine-source-and-version-resolution.md) and the
living [engine resolution contract](docs/engine-resolution.md) define how
that future engine is sourced, overridden locally, diagnosed, and rejected
when incompatible. [ADR 0012](docs/adr/0012-engine-dependency-update-policy.md)
and the living [engine update policy](docs/engine-updates.md) define how a
compatibility-line dependency update is adopted, how a breaking line is
crossed, and what automated dependency tooling may never do unattended.

The living [CLI UX and prompting conventions](docs/cli-conventions.md) define
input precedence, prompt-skipping rules, interactive/non-interactive parity,
validation ownership, and exit statuses. Changes to `cli.py`, `prompts.py`, or
their replacement at the public-engine cutover must update that contract and
its executable examples together when behavior changes.

## Commit messages

Conventional Commits (`feat:`, `fix:`, `chore:`, ...). A `commit-msg` hook
enforces this once `pre-commit install --install-hooks` has run.

## Labels

[.github/labels.toml](.github/labels.toml) is the source of truth for this
repo's issue and PR labels, and is shared with `forge-template` — the same
manifest drives both, so the two never drift into different vocabularies.
Six namespaced groups each use one colour family: `area:`, `type:`,
`priority:`, `size:`, `status:`, and `roadmap:`. Most `type:` labels mirror the
Conventional Commits prefixes above; `type:epic` and `type:decision` classify
roadmap planning rather than a single eventual commit. `good first issue`,
`help wanted`, `cross-repo`, and `breaking-change` stay unprefixed because
their repository-wide meaning is clearer without another namespace.

Apply the manifest to a repo with:

```bash
uv run poe labels:sync --dry-run                 # preview, changes nothing
uv run poe labels:sync --prune                   # apply, deleting extras
uv run python scripts/labels.py --repo Sandsy09/forge-template --prune
```

`gh label create --force` makes this idempotent — re-run it any time the
manifest changes. `tests/test_labels.py` validates the manifest's shape
(colour format, description length, no name collisions) in the fast suite.

## Releasing

`pyproject.toml`'s `version` is the single source of truth for a release's tag
— see [ADR 0009](docs/adr/0009-pyproject-as-the-single-version-source.md) for
why the release workflow itself does not choose a version bump.

1. Open a PR bumping `pyproject.toml`'s `version` and regenerating the
   changelog:

   ```bash
   uv run git-cliff --tag vX.Y.Z --output CHANGELOG.md
   ```

2. Merge it. Wait for `All checks passed` on `main`.
3. Actions → Release → Run workflow, with `dry_run` checked. Confirm the
   computed tag and generated notes in the run summary.
4. Run it again with `dry_run` unchecked. This tags `main`, pushes the tag, and
   publishes the GitHub release.
