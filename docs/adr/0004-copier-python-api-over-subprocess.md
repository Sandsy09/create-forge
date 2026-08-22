# 4. Copier's Python API over subprocess

## Status

Accepted

## Context

Having chosen Copier ([ADR 0002](0002-copier-over-cookiecutter.md)), this tool
still had to decide how to invoke it: shell out to the `copier` CLI as a
subprocess, or call `copier.run_copy` / `copier.run_update` directly as a
library. A subprocess would isolate this CLI from Copier's internals entirely,
at the cost of parsing Copier's human-oriented CLI output to detect what went
wrong.

## Decision

Call Copier's Python API directly, and confine every call to a single module:
`runner.py`. Nothing else in this codebase imports `copier`.

Copier raises structured exceptions (`CopierError`, `UserMessageError`) that
`runner._explain()` can pattern-match and rewrite into guidance a user who has
never heard of Copier can act on — "dirty working tree" becomes "commit or
stash first: git stash", for instance. A subprocess boundary would have turned
this into scraping stderr text that Copier does not guarantee to keep stable.

## Consequences

- **The `copier>=9.4,<10` pin in `pyproject.toml` is deliberately narrow.**
  Copier's Python API is public but evolves faster than its CLI's documented
  interface, so a major version bump is expected to need code changes. Because
  every touchpoint is confined to `runner.py`, that is the only file a bump
  should require attention in — see `CLAUDE.md` invariant 4.
- `runner.scaffold()` and `runner.update()` take and return this CLI's own
  types (`ScaffoldRequest`, plain exceptions), not Copier's — `cli.py` and
  `prompts.py` never see a Copier object.
- Testing scaffolds without a subprocess to mock: `tests/test_cli.py`
  monkeypatches `cli_module.scaffold` directly and asserts against the
  resolved `ScaffoldRequest`, which is possible only because there is no
  process boundary in between.
