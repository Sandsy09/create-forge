# Security Policy

## Scope

`create-forge` executes code from the templates it scaffolds.
[runner.py](src/create_forge/runner.py) passes `unsafe=True` to Copier because
templates declare `_tasks` — this is how a generated project arrives already
git-initialised with hooks installed, and it is also a trust boundary: whatever
is cloned, runs.

That is the default trust boundary because template addresses are **bundled** in
[templates.toml](src/create_forge/templates.toml) — compiled into each
release rather than fetched at runtime or read from user configuration
(`config.toml` cannot set a template URL; see [config.py](src/create_forge/config.py)).
The only code trusted by default is code published alongside the tool.

`--template-url` is the sanctioned escape hatch for scaffolding from anywhere
else. It runs that source's code too, and prompts for confirmation before
doing so. Point it only at repositories you trust.

Template sources must not embed credentials. `new --template-url` and
`update`'s recorded `.copier-answers.yml` `_src_path` reject HTTP(S) user-info
(including username-only and encoded forms), SSH URL passwords, and URL
queries or fragments. Use a credential-free HTTPS URL with an external Git
credential helper, or SSH with an SSH agent; select versions with `--ref`.
Ordinary SSH usernames, SCP-style sources, Copier shorthand and local paths
remain supported. The same checks cover Copier's `git+` URL prefix.

Rejection happens before prompts or generation effects; an unsafe recorded
update source is rejected before Copier runs, without changing the project.
Replace that recorded source with its credential-free equivalent before
retrying. Malformed answers files are reported without quoting YAML content.
Warnings display source text literally and strip URL authentication, queries,
and fragments defensively. Expected Copier/Git failures use fixed guidance,
never raw process output or unknown exception text. Internal exception causes
are retained for debugging and must not be logged or rendered to users.
These safeguards do not sandbox trusted template tasks or manage credentials
stored by Git, shells, or other external tools. See
[ADR 0036](docs/adr/0036-template-source-credentials.md).

The release and documentation workflows are a second supply-chain boundary:
they hold `contents: write`, `id-token: write` (PyPI Trusted Publishing) and
`pages: write`. Every external GitHub Action is pinned to a full commit SHA so
a moved tag cannot change the code a privileged job runs, and workflow-level
token permissions are read-only with `write`/`id-token` scopes only on the
individual jobs that need them. `scripts/check_workflows.py` enforces
both in CI, and a Dependabot Action bump is merged only after its proposed SHA
is confirmed against the tag it claims. See
[ADR 0037](docs/adr/0037-immutable-workflow-actions.md) and the
[workflow security contract](docs/workflow-security.md).

A vulnerability in how `create-forge` itself handles this trust boundary — for
example, a way to reach `unsafe=True` behaviour from the bundled registry
without `--template-url`, or a way for `config.toml` to influence which code
runs — is in scope here. A bug in the *content* generated projects ship with
belongs in [forge-template](https://github.com/Sandsy09/forge-template)
instead; the two repos are deliberately separate (see `CLAUDE.md`).

## Accepted engine transition

The future [public-engine integration contract](docs/integration-contract.md)
moves Copier and template execution behind a versioned `forge-template` API
without widening the trust boundary. Normal discovery remains limited to
metadata and executable assets shipped in the reviewed engine release. Runtime
remote registries and arbitrary component plugins are not accepted.

At the coordinated cutover, an explicit, warned, contract-compatible local or
VCS engine override — `--engine-source`/`--engine-ref`, per
[ADR 0011](docs/adr/0011-engine-source-and-version-resolution.md) — replaces
arbitrary `--template-url` execution. Unsupported engine or ProjectSpec
protocol versions fail before discovery, template tasks or destination
writes, exiting with a dedicated status (`3`) and no silent direct-Copier
fallback; see the [engine resolution contract](docs/engine-resolution.md).
The hidden `--engine-preview` path already performs package and protocol
negotiation and uses exit status `3` for incompatibility. The default `new`
path is still direct-Copier, however, and `--engine-source`/`--engine-ref` do
not exist yet. Making the engine the default and adding those override flags
remain one future, coordinated cutover.

Automated dependency tooling cannot cross either compatibility line (`copier`
for the default path or `forge-template` for the preview path) on its own —
[ADR 0012](docs/adr/0012-engine-dependency-update-policy.md) restricts
Dependabot to proposing updates within each declared range; crossing one
requires a deliberate, human-authored pull request. See the
[engine update policy](docs/engine-updates.md).

## Supported versions

Only the latest tagged release is supported. There is no backport policy.

## Reporting a vulnerability

Do not open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/Sandsy09/create-forge/security/advisories/new)
to report privately.

You should get an acknowledgement within a few business days.
