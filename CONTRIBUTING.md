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

## Before opening a pull request

```bash
uv run poe check
```

Runs `ruff format --check`, `ruff check`, `mypy`, and the fast test suite —
`pytest -m 'not network'`.

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
| `network` | `pytest -m network` — the `copier.yml` drift guard, plus the real `update()` end-to-end |
| `all-green` | an aggregate check; this is the one branch protection requires |

`network` also runs on a Monday cron, independent of any push here —
`forge-template` moves on its own schedule, so a PR is not the only thing that
can surface a registry mismatch.

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
[integration contract](docs/integration-contract.md). The current v0.1.x
Copier/registry implementation remains authoritative until that contract is
implemented as one coordinated cutover.

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
