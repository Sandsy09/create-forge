# Forge Integration Contract

This is the living operational contract between `create-forge` and
`forge-template`. [ADR 0010](adr/0010-public-engine-integration-contract.md)
records why Forge adopted the public-engine direction; this document records
the compatibility rules that later releases must keep current.

## Status

The public engine is the accepted target architecture. Strict
[ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
and [component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
are implemented by `forge-template` together with the
[stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md),
recorded by [ADR 0029](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0029-stable-template-engine-api.md).
The canonical
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md),
recorded by [ADR 0030](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0030-generated-project-validation.md),
now validates rendered output in memory before the engine returns it.
The accepted
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md),
recorded by
[forge-template ADR 0031](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0031-library-archetype-contract.md),
defines the first production component, the manifest protocol `2`, option
schema `2`, implicit Foundation source, and `0.3.0` planning-owner migration
now implemented on `forge-template/main`. The accepted
[CLI Application archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md),
recorded by
[forge-template ADR 0034](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0034-select-cli-application-reference-archetype.md),
selects the optionless engine-owned `cli` archetype. Its console command is
derived from `ProjectSpec.project.repository_name`; FT-08.04 owns its future
manifest and content.
This repository's exact development line is now `forge-template==0.3.0`
(CF-08.02, [ADR 0017](adr/0017-cli-application-archetype-exposure.md)),
whose production catalogue ships both `library` and `cli`. Development-only
ProjectSpec construction, component-discovery, validation, and rendering
adapters exist and are tested against that exact development pair, and are
reachable — behind the hidden `new --engine-preview` flag, with a
discovery-driven `--archetype` selection — for both production archetypes.
The released v0.1.x CLI remains a thin Copier wrapper with a bundled
registry, and its current security and update invariants remain
authoritative until the coordinated cutover.

| create-forge line | forge-template engine range | ProjectSpec protocol | Status |
| --- | --- | --- | --- |
| v0.1.x | None; direct Copier integration | None | Current released architecture |
| First engine line | Unassigned | 1 (defined; not yet supported) | Stage 06 development contract tested; distribution and CLI cutover pending |

The separate development contract is `forge-template==0.3.0` at tag
`v0.3.0`, ProjectSpec protocol `1`, and component-manifest protocol
`(1, 2)`. The canonical
[cross-repository engine contract tests](engine-contract-tests.md) make that
pair executable. It is deliberately not the first row's installable range.
The Library migration and CLI Application implementation are what CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) adopted this
exact pair to consume: its production-catalogue expectation replaces the
prior `0.2.0`/empty-catalogue one, and the released range remains
unassigned here regardless.
CF-07.04 ([ADR 0015](adr/0015-staged-filesystem-generation.md)) moved this
pin forward from Stage 06's original revision specifically to adopt the
generated-project validator: `render_project` now calls the public
`validate_rendered_project` before returning, which is what lets
`create-forge` finalise a rendered project to disk on the strength of the
engine's own in-memory check rather than reimplementing it. CF-08.02 moved
it again, from that commit to the `v0.3.0` tag.

Protocol 1 is assigned by
[forge-template ADR 0023](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0023-projectspec-protocol-v1.md).
It is not a protocol supported by any released `create-forge` line yet. Do not
assign the future engine range or mark the pair supported by a released CLI
until #9 resolves distribution and a future cutover issue completes the
atomic cutover with released lower/latest compatibility tests.

[Forge-template ADR 0024](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0024-component-manifest-protocol-v1.md)
assigns component manifest protocol `1`. It defines strict bundled identity,
display, version, compatibility, content, dependency, and conflict metadata;
it does not make component discovery available to a released CLI line.

[ADR 0011](adr/0011-engine-source-and-version-resolution.md) and the canonical
[engine resolution contract](engine-resolution.md) define how the remaining
engine-range cell gets filled — a bounded, install-time dependency plus an
explicit, warned local/VCS override — without assigning that range here.

[ADR 0013](adr/0013-projectspec-construction-boundary.md) adds a
ProjectSpec-building boundary (`src/create_forge/spec.py` and
`src/create_forge/engine.py`) ahead of this row being filled in — a
development-only dependency pinned to a commit, not the runtime range this
table records. `create-forge new` does not call it yet; see the canonical
[ProjectSpec construction contract](project-spec-construction.md).

The canonical [component discovery contract](component-discovery.md) adds a
second operation to that same boundary. It negotiates both the ProjectSpec and
component-manifest protocols before calling the public engine and returns the
engine's descriptors unchanged. It assigns no package range and is likewise
unreachable from the released CLI.

The canonical [cross-repository engine contract tests](engine-contract-tests.md)
then prove the exact development package/protocol pair and the public
discovery, validation, and rendering boundary without changing that released
compatibility table.

## Ownership and dependency direction

`create-forge` owns user interaction: commands, flags, prompts, user-facing
validation, ProjectSpec construction, diagnostics and safe filesystem
orchestration. `forge-template` owns the canonical ProjectSpec types and
validation, component manifests, discovery and compatibility, composition,
rendering, Copier integration, and generated content. The canonical
[filesystem generation contract](filesystem-generation.md) records the
client-side staging, finalisation, and cleanup rules that safe filesystem
orchestration implies, behind the same hidden `--engine-preview` flag as the
rest of this boundary.

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

A `forge-template` release is one installable unit containing its engine,
component manifests, and reviewed template assets. Its package version,
ProjectSpec protocol, manifest protocol, and bundled component versions are
related but independent:

- For `forge-template` versions below 1.0, a supported dependency range stays
  within one minor line, such as `>=0.y.a,<0.(y+1)`.
- From 1.0 onward, a supported range stays within one major line, such as
  `>=n.a,<n+1`.
- Every dependency declaration has a tested lower bound and a strict upper
  bound. An unbounded engine dependency is unsupported.
- The canonical
  [ProjectSpec protocol](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
  carries explicit version `1`. Breaking serialisation,
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

The engine-owned
[manifest contract](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
is the sole component metadata source. `create-forge` must not retain its
bundled registry as a fallback or recreate compatibility, dependency, or
conflict rules after cutover. The client-side mechanics and current pre-cutover
status are recorded in the [component discovery contract](component-discovery.md).

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
