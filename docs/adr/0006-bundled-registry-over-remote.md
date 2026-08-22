# 6. Bundled registry over remote

## Status

Accepted

## Context

`templates.toml` — the registry of known templates and their prompts — has to
live somewhere the CLI can read it from. Two shapes were available: ship it as
package data inside the `create-forge` wheel, versioned and released together
with the tool; or fetch it from a URL at runtime, so new templates or prompt
changes reach users without a `create-forge` release.

A remote registry is the more flexible design in isolation — new templates
would appear without users updating their `uvx create-forge` install. But
[ADR 0005](0005-execute-template-tasks.md) already commits this tool to
running whatever `_tasks` a template declares. A registry that could be
changed after release would mean the thing being trusted — which template
URLs get run with `unsafe=True` — is no longer fixed by the reviewed code the
user installed.

## Decision

Bundle `templates.toml` as package data (`src/create_forge/templates.toml`,
loaded and validated by `registry.py`), shipped in the wheel and versioned
with every release. No remote fetch, no config-based URL override for the
default registry.

## Consequences

- **`unsafe=True` stays justified.** The only code trusted by default is code
  published alongside the tool's own reviewed release — see ADR 0005. Adding
  remote registry fetching or a config-based URL override without revisiting
  that decision would quietly undermine it.
- **New templates require a `create-forge` release**, not just a
  `forge-template` tag. This is the trade this design accepts: template
  content updates freely (`copier update` picks up new tags immediately), but
  which templates exist and what they prompt for is fixed until the CLI itself
  is updated.
- **`CLAUDE.md` invariant 5** — `templates.toml` must ship in the wheel — exists
  because this decision makes that file load-bearing at runtime in every
  install, not just in editable/source checkouts. `scripts/check_wheel.py`
  (`poe check:wheel`) guards it.
- A remote registry override remains explicitly deferred (see `CLAUDE.md`'s
  backlog), and would need a signing or allowlist mechanism designed first —
  not merely a config flag — before it could be added without reopening this
  decision.
