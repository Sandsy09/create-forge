# Forge Integration Contract

This is the living operational contract between `create-forge` and
`forge-template`. [ADR 0010](adr/0010-public-engine-integration-contract.md)
records why Forge adopted the public-engine direction; this document records
the compatibility rules that later releases must keep current.

## Status

The public engine is the accepted target architecture but is not implemented.
The released v0.1.x CLI remains a thin Copier wrapper with a bundled registry,
and its current security and update invariants remain authoritative until the
coordinated cutover.

| create-forge line | forge-template engine range | ProjectSpec protocol | Status |
| --- | --- | --- | --- |
| v0.1.x | None; direct Copier integration | None | Current released architecture |
| First engine line | Unassigned | Unassigned | Accepted target, not yet available |

Do not fill the future row speculatively. Record concrete values only when the
engine package and ProjectSpec schema exist and their compatibility tests pass.
[ADR 0011](adr/0011-engine-source-and-version-resolution.md) and the canonical
[engine resolution contract](engine-resolution.md) define *how* that row gets
filled in — a bounded, install-time dependency plus an explicit, warned
local/VCS override — without assigning it here.

## Ownership and dependency direction

`create-forge` owns user interaction: commands, flags, prompts, user-facing
validation, ProjectSpec construction, diagnostics and safe filesystem
orchestration. `forge-template` owns the canonical ProjectSpec types and
validation, component discovery and compatibility, composition, rendering,
Copier integration, and generated content.

The dependency is one-way:

```text
User
  ↓
create-forge
  ↓  versioned ProjectSpec / public engine contract
forge-template
  ↓
Generated project
```

`forge-template` must not depend on `create-forge`. Generated projects must
remain independent of both packages during normal development and runtime.

## Version and protocol compatibility

A `forge-template` release is one installable unit containing its engine and
reviewed template assets. Its package version and the ProjectSpec protocol are
related but independent:

- For `forge-template` versions below 1.0, a supported dependency range stays
  within one minor line, such as `>=0.y.a,<0.(y+1)`.
- From 1.0 onward, a supported range stays within one major line, such as
  `>=n.a,<n+1`.
- Every dependency declaration has a tested lower bound and a strict upper
  bound. An unbounded engine dependency is unsupported.
- ProjectSpec carries an explicit protocol version. Breaking serialisation,
  validation or semantic changes increment it; backward-compatible additions
  may remain on the current protocol.
- Each `create-forge` release documents the engine range and protocol versions
  it accepts. Contract tests exercise the supported pair before release.

## Unsupported combinations

Compatibility is checked before component discovery, rendering, template task
execution or destination writes. A mismatch must:

1. fail closed with no automatic direct-Copier or bundled-registry fallback;
2. identify the detected engine package and ProjectSpec protocol;
3. state the supported range or versions; and
4. give a concrete upgrade, downgrade or source-correction action.

CLI diagnostics must report the `create-forge` version, `forge-template`
package version, supported and detected ProjectSpec protocols, and the
template/asset release needed to reproduce a generation failure.

## Source and trust policy

Normal operation discovers components and executes assets only from the
installed, version-constrained `forge-template` release. A remote registry or
arbitrary installed component plugin cannot change executable sources at
runtime.

Cross-repository development may use an explicit local or VCS engine override.
The user must select it deliberately, receive a code-execution warning, and
pass the same public-contract compatibility check before rendering. Ordinary
saved CLI configuration cannot silently redirect the engine or template
source.

[ADR 0011](adr/0011-engine-source-and-version-resolution.md) names that
override `--engine-source`/`--engine-ref` and, symmetrically, reserves exit
status `3` exclusively for a failed compatibility check — see the
[engine resolution contract](engine-resolution.md) for both. Neither ships
before the engine cutover.

At the engine cutover this compatible override replaces the current arbitrary
`--template-url` option. The v0.1.x option and warning remain supported until
then; there is no dual direct-Copier path afterward.

## Release coordination

Compatible `forge-template` releases may be adopted within the declared range
only after contract and end-to-end tests pass. [ADR 0012](adr/0012-engine-dependency-update-policy.md)
and the canonical [engine update policy](engine-updates.md) define that
adoption rule in full — the CI proof a compatibility-line bump requires, and
why automated dependency tooling (`.github/dependabot.yml`) is restricted to
proposing updates inside a declared range, never across one. A breaking
integration change uses this order:

1. release a new `forge-template` compatibility line, including engine and
   reviewed assets;
2. publish compatibility and generated-project migration notes;
3. prove ProjectSpec, discovery, rendering and existing-project update paths
   against the exact pair; and
4. release the adopting `create-forge` line with matching bounds.

Earlier `create-forge` releases retain their prior dependency bounds. Existing
generated projects must have a supported update path or a documented, tested
migration before the new client is released.

## Downstream and organisation integrations

Blueprint-style clients consume `forge-template` directly and apply policy as
validated ProjectSpec inputs. They do not depend on `create-forge` internals,
and policy does not gain an arbitrary file or code-execution hook.

Organisations may still fork for genuinely custom executable template content.
That is distinct from the preferred downstream-client path for defaults,
required selections and forbidden selections.
