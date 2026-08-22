# 5. Execute template tasks (`unsafe=True`)

## Status

Accepted

## Context

Copier templates can declare `_tasks` in `copier.yml` — commands that run
after the files are rendered. `forge-template` uses this to git-initialise a
generated project and install its pre-commit hooks, so it arrives ready to
commit rather than as an inert pile of files. Copier requires an explicit
opt-in to run them (`--trust` on the CLI, `unsafe=True` on the Python API),
because a template's tasks are arbitrary code and Copier has no way to know,
in general, what a given template's tasks will do.

The alternative was real: refuse `_tasks` entirely and ship a plainer scaffold
— files only, no git init, no hooks installed, the user runs a documented
setup command afterward by hand.

## Decision

Pass `unsafe=True` in `runner.scaffold()` and `runner.update()`, and accept the
post-generation setup this buys — a project that arrives already
git-initialised, hook-installed, and ready to commit.

This is acceptable specifically *because* of a second decision this one
depends on: template URLs are compiled into each `create-forge` release rather
than fetched at runtime or read from user configuration ([ADR
0006](0006-bundled-registry-over-remote.md)). The only code trusted by default
is code published alongside this tool's own reviewed release, not something an
attacker could redirect at runtime.

## Consequences

- `unsafe=True` is load-bearing and dangerous in the general case — see
  `CLAUDE.md` invariant 3. It is safe here only as long as the constraint in
  ADR 0006 holds. Any change that lets a template URL be supplied or
  overridden outside of a reviewed release (remote registry fetching,
  config-based URL overrides) revisits this decision, not just that one.
- `--template-url` is the sanctioned escape hatch for a template outside the
  bundled registry, and it prompts for confirmation before running — the one
  place in this CLI where a user is knowingly opting into code execution from
  a source the maintainers have not reviewed.
- `README.md`'s Security section exists because of this decision: users are
  told plainly that scaffolding executes code from the template it clones, and
  are pointed at `SECURITY.md` for reporting rather than filing a public issue.
