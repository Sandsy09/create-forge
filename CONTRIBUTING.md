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

This hits GitHub and includes `tests/test_drift.py`, which clones
`forge-template` and checks every prompt key in `templates.toml` still matches
a question in its `copier.yml`. That check exists because a mismatch fails
*silently* — Copier drops an unknown `data` key with no error, the answer
vanishes, and the template's own default applies instead. A typo here produces
a scaffold that looks fine and is subtly wrong, which is exactly the failure
mode this test is for. Run it whenever `templates.toml` changes, or whenever
`forge-template` cuts a new tag.

Before any release, also run:

```bash
uv run poe check:wheel
```

Editable installs read `templates.toml` from source; a built wheel does not
unless Hatchling's package-data rules are still correct. A missing registry
passes every test above and only breaks on a user's first `uvx` run — this is
the one check that catches it ahead of time.

## Commit messages

Conventional Commits (`feat:`, `fix:`, `chore:`, ...). A `commit-msg` hook
enforces this once `pre-commit install --install-hooks` has run.

## Releasing

There is no release workflow yet — see
[issue #7](https://github.com/Sandsy09/create-forge/issues/7). Until it lands,
treat `main` as the only supported state; there is nothing to release against.
