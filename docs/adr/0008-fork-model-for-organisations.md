# 8. Fork model for organisations

## Status

Accepted

## Context

Organisations adopting this tool will generally need templates it cannot
anticipate — internal registries, mandated scanners, approval workflows,
house conventions that have nothing to do with an open-source scaffolding
CLI. Two shapes were available: build configurability into `create-forge`
itself (a remote or pluggable registry, organisation-specific hooks), or point
organisations at forking the repository and maintaining their own registry.

A built-in mechanism was rejected primarily because of
[ADR 0006](0006-bundled-registry-over-remote.md): a registry that can be
pointed at arbitrary URLs at runtime is exactly the thing that decision
declines to build, since `unsafe=True` ([ADR 0005](0005-execute-template-tasks.md))
depends on the registry being fixed at release time.

## Decision

The supported path for organisation-specific templates is forking this
repository, replacing `templates.toml` (and the template repositories it
points at) with the organisation's own, and maintaining that fork internally.

The core modules (`models.py`, `registry.py`, `prompts.py`, `runner.py`,
`cli.py`) are kept deliberately template-agnostic — none of them hardcode
anything about `forge-template` specifically — so that a fork whose only
change is `templates.toml` stays easy to merge upstream changes into.

## Consequences

- An organisation gets full control over which templates are offered and what
  they prompt for, without this project needing to design a plugin or
  override mechanism for a use case it cannot test against.
- Staying mergeable from upstream is a convention this repo has to uphold, not
  something enforced by tooling: any future change that makes `templates.toml`
  content leak into `models.py`, `prompts.py`, or `cli.py` logic would make
  forks harder to maintain, even though nothing here would fail a test over
  it.
- This is a documentation-only decision — `README.md`'s "Using this at work"
  section is the user-facing statement of it. There is no code enforcing that
  a fork stays clean; that is a matter of code review discipline in this repo
  going forward.
