# 11. Resolve the template engine from a bounded installed dependency

## Status

Accepted

## Context

[ADR 0010](0010-public-engine-integration-contract.md) accepted a versioned
public `forge-template` engine as `create-forge`'s long-term integration
target, and the [integration contract](../integration-contract.md) records
the compatibility rules a later release must keep current. Both deliberately
left the mechanics open and assigned them to CF-04.01
([issue #44](https://github.com/Sandsy09/create-forge/issues/44)):

- how a normal, installed/released `create-forge` obtains the versioned
  engine-and-assets unit;
- what the explicit, warned local/VCS engine override looks like for
  cross-repository development, given it replaces the current
  `--template-url` escape hatch only at the coordinated cutover;
- which CLI, engine-package, ProjectSpec-protocol and template/asset versions
  diagnostics must report to make a compatibility failure reproducible; and
- what unsupported source or version behaviour is, without letting a
  generated project's own configuration leak into CLI settings.

The engine package does not exist yet. `forge-template`'s own
`pyproject.toml` still classifies it `Private :: Do Not Upload`, and exposing
a stable engine API is forge-template's own open `FT-06.07`. ADR 0010 is
explicit that the first concrete engine range and ProjectSpec protocol number
must not be reserved speculatively — they are assigned once the package and
schema exist and their compatibility tests pass. This decision therefore
defines the resolution *rules and interfaces*, not a version number.

## Decision

**Normal installed/released resolution.** A `create-forge` release obtains
the engine the same way it obtains any other library: as an ordinary,
version-bounded dependency declared in its own `pyproject.toml`, resolved by
the installer (`uv`/`pip`) at install time. Once installed, `create-forge`
imports it like any dependency. There is no runtime fetch, clone, or download
of executable content — this is what carries ADR 0005's trust principle
("code is executed by default only when it shipped in the reviewed release")
across the engine cutover instead of weakening it.

Following the integration contract's compatibility rule, the declared range
stays within one minor line before `forge-template` 1.0
(`>=0.y.a,<0.(y+1)`) and one major line from 1.0 onward (`>=n.a,<n+1`), with
both a tested lower bound and a strict upper bound. Which index or channel
that dependency resolves from — a package index, a pinned VCS revision, or
another mechanism — is a distribution-channel decision, not a resolution-rule
decision, and is deliberately deferred to CF-05.02
([issue #45](https://github.com/Sandsy09/create-forge/issues/45)) and
PyPI publishing ([issue #9](https://github.com/Sandsy09/create-forge/issues/9)).
This decision does not assign the first concrete range or protocol number;
[`docs/engine-resolution.md`](../engine-resolution.md) records the checklist
for assigning it once the package exists.

**Local/VCS development override.** Cross-repository development gets an
explicit override, distinct from ordinary configuration: `--engine-source`
(a local path or a VCS URL) and `--engine-ref` (a ref within that source;
valid only alongside `--engine-source`, and an error on its own). Selecting
it always prints the existing code-execution warning and, unless `--yes` is
given, requires confirmation — `--yes` may skip the confirmation prompt but
never the warning. Content resolved through the override must pass the same
public-contract compatibility check as an installed engine before any
discovery, rendering, template task execution, or destination write. This is
the interface ADR 0010 named as `--template-url`'s eventual replacement; it
is specified here but, per the next section, does not ship in this change.

Ordinary saved configuration can never select an engine source. `config.toml`
and `FORGE_*` environment variables remain answer-preset conveniences; no
field on either is a source, engine, range, or protocol selector, and
`UserConfig`'s `extra="forbid"` model configuration makes an attempt to add
one a validation error rather than a silent new capability. This is the
"generated-project configuration must not leak into CLI settings" guarantee:
a project's own recorded engine version stays in that project's own
engine-owned answers file, never promoted into the user's CLI-wide config.

**Diagnostics.** A reproducible compatibility failure requires the CLI
version, Python version and platform, the active integration line, the
engine package name and installed version (or its absence, before cutover),
the range `create-forge` supports, the supported and detected ProjectSpec
protocol, and the resolved template/asset release. `docs/engine-resolution.md`
records the exact field list and its machine-readable form, split into what
is reportable today under the v0.1.x direct-Copier line and what becomes
reportable once the engine exists.

**Unsupported combinations.** An engine package or ProjectSpec protocol
outside the supported range must fail closed *before* component discovery,
rendering, template task execution, or any destination write, with the
detected version, the supported range, and one concrete remediation
(upgrade, downgrade, or source correction) in the error. There is no
automatic fallback to the bundled registry or direct Copier. This class of
failure uses a dedicated exit status, `3`, reserved exclusively for it, so
scripts and CI can distinguish "incompatible engine" from any other
application error (`docs/cli-conventions.md`'s existing `1`).

**Timing.** These interfaces are specified now; they ship at the coordinated
engine cutover, in the same atomic release ADR 0010 describes. Until then,
the v0.1.x direct-Copier line, its existing `--template-url`/`--ref` options,
and their existing warning remain the only implementation, unchanged. No new
CLI flag is added by this decision.

## Consequences

- A broken or incompatible environment surfaces at install/resolve time for
  the normal path, rather than mid-scaffold — the same failure mode as any
  other missing or misversioned Python dependency, which is more familiar to
  operators than a runtime fetch failure would be.
- Exit status `3` is a new element of the CLI's compatibility contract;
  `docs/cli-conventions.md`'s exit-status table gains a row for it, marked
  reserved until the engine cutover raises it for the first time.
- CF-05.02 inherits a narrower, well-scoped question — which distribution
  channel and update cadence — rather than the whole resolution mechanism.
- `--ref` currently selects an arbitrary template tag under direct Copier
  integration. Once template/asset versions are bound to the engine
  package's own version, `--ref` has no remaining meaning for the normal
  path and is removed at the same cutover that removes the direct-Copier
  path; `--engine-ref` is scoped only to the explicit override. This is a
  breaking CLI change that the cutover release's notes must call out
  explicitly.
- Until the cutover, nothing in this decision changes v0.1.x behaviour:
  `--template-url` keeps its current meaning, warning, and confirmation
  flow, and the bundled registry keeps resolving the latest PEP 440 tag.
