# 2. Copier over Cookiecutter

## Status

Accepted

## Context

Cookiecutter is the more widely known scaffolding tool, but it only copies
files once. A project generated from a Cookiecutter template has no supported
way to pull in template changes made after it was scaffolded — the template
and every project it already produced drift apart from the moment of
generation.

## Decision

Build on [Copier](https://copier.readthedocs.io/) instead, and scaffold from
`forge-template`, which is itself a Copier template. Copier's defining feature
is `copier update`, which three-way merges template changes into a project
generated months (or years) earlier, using the answers recorded at scaffold
time (`.copier-answers.yml`) as the common ancestor. `create-forge update`
(`runner.py`'s `update()`) is a thin wrapper over exactly that.

This is the reason `create-forge` exists as a distinct tool rather than a
one-line `cookiecutter gh:...` recommendation in `forge-template`'s README: a
generator that cannot express "pull in what changed" is not solving the
problem this project cares about.

## Consequences

- **Every user-visible change to `forge-template` needs a tag.** Copier
  resolves a template's "latest version" from PEP 440 git tags; untagged
  commits on `forge-template`'s `main` are invisible to `create-forge new` and
  `update` alike. This is also why the templates and the CLI cannot live in
  one repository — see [ADR 0003](0003-two-repo-split.md).
- **`create-forge` inherits Copier's Python API surface rather than shelling
  out to its CLI** — see [ADR 0004](0004-copier-python-api-over-subprocess.md).
- **The `--ref` flag on `new` and `update`, and the `vcs_ref` field on
  `ScaffoldRequest`, exist only because Copier resolves versions this way** —
  there is no equivalent concept to expose for a tool that only ever copies
  once.
- A known Copier limitation is inherited, not fixed: local edits at the very
  end of a templated file can be lost on `update`, since both sides append at
  EOF with no trailing context for the merge to anchor to. That is
  `forge-template`'s problem to design around, not this CLI's.
