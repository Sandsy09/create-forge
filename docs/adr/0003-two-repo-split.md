# 3. Two-repo split

## Status

Accepted

## Context

`create-forge` (this repo, the CLI) and `forge-template` (the templates it
scaffolds from) could plausibly live in one repository — this tool is, in the
end, a thin wrapper around `copier copy gh:Sandsy09/forge-template`. But
[ADR 0002](0002-copier-over-cookiecutter.md) established that Copier resolves
a template's "latest version" from PEP 440 git tags on the *template's own*
repository.

## Decision

Keep them as two separate repositories:

| Repo | Role |
| --- | --- |
| [`create-forge`](https://github.com/Sandsy09/create-forge) | This repo. The CLI. |
| [`forge-template`](https://github.com/Sandsy09/forge-template) | The templates it scaffolds from. |

If they were one repository, every tag would have to mean something for both
the CLI's release cadence and the templates' — a CLI bugfix release would
either need its own unrelated template tag, or template changes would have to
wait on a CLI release to ship. Splitting removes that coupling: `forge-template`
tags exist purely to mark points `copier update` can resolve to, and
`create-forge` is versioned and released as its own package.

## Consequences

- A change spanning both (e.g. this CLI needing a new template question)
  requires two PRs, in two repos, potentially reviewed and merged out of
  order. `CLAUDE.md`'s invariant 1 — every registry prompt key must exist in
  `forge-template`'s `copier.yml` — exists because this ordering can go wrong
  silently; `tests/test_drift.py` guards it.
- `create-forge` supplies context the template itself deliberately leaves
  blank — e.g. `copier.yml`'s `github_org` question has an empty default
  because this CLI's own config (`config.py`) fills it in; a bare
  `copier copy` user is simply prompted.
- Each repo has its own CI, its own `pyproject.toml`, and its own release
  workflow, with no shared tooling repo to keep in sync.
- The registry (`templates.toml`) is the seam between the two repos — it names
  which `forge-template` archetypes exist and where their prompts live, but
  never their content. See [ADR 0006](0006-bundled-registry-over-remote.md)
  for why that registry ships compiled into `create-forge` rather than being
  fetched at runtime.
