# Security Policy

## Scope

`create-forge` executes code from the templates it scaffolds.
[runner.py](src/create_forge/runner.py) passes `unsafe=True` to Copier because
templates declare `_tasks` — this is how a generated project arrives already
git-initialised with hooks installed, and it is also a trust boundary: whatever
is cloned, runs.

That is acceptable only because template addresses are **bundled** in
[templates.toml](src/create_forge/templates.toml) — compiled into each
release rather than fetched at runtime or read from user configuration
(`config.toml` cannot set a template URL; see [config.py](src/create_forge/config.py)).
The only code trusted by default is code published alongside the tool.

`--template-url` is the sanctioned escape hatch for scaffolding from anywhere
else. It runs that source's code too, and prompts for confirmation before
doing so. Point it only at repositories you trust.

A vulnerability in how `create-forge` itself handles this trust boundary — for
example, a way to reach `unsafe=True` behaviour from the bundled registry
without `--template-url`, or a way for `config.toml` to influence which code
runs — is in scope here. A bug in the *content* generated projects ship with
belongs in [forge-template](https://github.com/Sandsy09/forge-template)
instead; the two repos are deliberately separate (see `CLAUDE.md`).

## Supported versions

Only the latest tagged release is supported. There is no backport policy.

## Reporting a vulnerability

Do not open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/Sandsy09/create-forge/security/advisories/new)
to report privately.

You should get an acknowledgement within a few business days.
