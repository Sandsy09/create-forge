# 9. `pyproject.toml` as the single version source

## Status

Accepted

## Context

`forge-template`'s release workflow — the one issue [#7](https://github.com/Sandsy09/create-forge/issues/7)
asked this repo's own workflow to be ported from — takes a `patch`/`minor`/
`major` bump choice as a `workflow_dispatch` input, computes the next tag by
incrementing whatever the latest git tag is, and pushes that tag directly.
That works there because `forge-template` is a template repository with no
installable package and no `--version` flag: the tag is the only version that
exists.

`create-forge` is different. [`pyproject.toml`](../../pyproject.toml) already
carries a real `version`, hatchling bakes it into the wheel, and
[`_version()`](../../src/create_forge/cli.py) reads it back at runtime via
`importlib.metadata` for `create-forge --version`. Porting the bump-choice
model verbatim would create two independent version numbers — the git tag
Copier resolves templates against, and the string a user's installed CLI
actually reports — with nothing keeping them equal. A `minor` dispatch would
tag `v0.2.0` while every `create-forge --version` continued to print `0.1.0`
until someone noticed.

Keeping them in step by having the workflow edit `pyproject.toml` and commit
that bump to `main` was considered and rejected: branch protection on `main`
requires a pull request plus the `All checks passed` status check (confirmed
via the GitHub API), so a bot commit pushed directly by the release job would
be rejected outright, and even a `github.token`-authored push that somehow
landed would not itself trigger `ci.yml`.

## Decision

The release workflow does not choose a version. It reads whatever version is
already committed in `pyproject.toml`, using `tomllib` rather than a text
match, derives the tag as `v<version>`, and refuses to proceed if that tag
already exists.

Bumping the version is therefore an ordinary, reviewable pull request like any
other change: edit `pyproject.toml`, regenerate `CHANGELOG.md` with
`uv run git-cliff --tag vX.Y.Z --output CHANGELOG.md`, merge it, then dispatch
the release workflow against the resulting `main`. See
[`CONTRIBUTING.md`](../../CONTRIBUTING.md)'s Releasing section for the exact
steps.

## Consequences

- The tag and `create-forge --version` can never disagree — there is only ever
  one place the version is written.
- Releasing is deliberately two steps instead of one: a version-bump PR, then a
  dispatch. This is slower than `forge-template`'s single dispatch, in exchange
  for the version bump going through the same review and CI gate as any other
  change, rather than being decided silently inside a workflow run.
- The release workflow's tag-exists guard is what makes this safe: dispatching
  without having bumped `pyproject.toml` first fails loudly rather than
  silently re-tagging the same version or drifting past it.
- `forge-template`'s bump-choice model is not wrong for that repo — it has no
  package version to keep in sync with. This decision is specific to
  `create-forge` being an installable package, not a blanket preference over
  the sibling repo's approach.
