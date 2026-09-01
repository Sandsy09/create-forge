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
derived from `ProjectSpec.project.repository_name`; FT-08.04 implemented its
manifest and content, exposed here by CF-08.02.
The Stage 08
[composition architecture review](https://github.com/Sandsy09/forge-template/blob/main/docs/composition-architecture-review.md)
and
[ADR 0037](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0037-two-archetype-composition-review.md)
were released in `forge-template 0.3.2`. They preserve the public facade and
protocols while making the client responsible for dynamic lock finalisation.

[#9](https://github.com/Sandsy09/create-forge/issues/9) and
[ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md) assign
this repository's **first released engine range**:
`forge-template>=0.3.1,<0.4`, declared as the optional `engine` extra
(`create-forge[engine]`) rather than a `[project.dependencies]` entry or a
development-only pin. ProjectSpec construction, component-discovery,
validation, and rendering adapters are tested against that real, installed
range, and are reachable — behind the hidden `new --engine-preview` flag,
with a discovery-driven `--archetype` selection — for both production
archetypes. **This is not the CLI cutover.** The released default `new`
command remains a thin Copier wrapper with a bundled registry, and its
current security and update invariants remain authoritative until a future,
still-unfiled cutover replaces it.

| create-forge line | forge-template engine range | ProjectSpec protocol | Status |
| --- | --- | --- | --- |
| v0.1.x | None; direct Copier integration | None | Superseded by v0.2.x |
| v0.2.x (`engine` extra) | `forge-template>=0.3.1,<0.4` | 1 (supported) | Current released architecture (ADR 0018) |

`forge-template` `0.3.1` -- a packaging-only patch over the `0.3.0` production
catalogue CF-08.02 adopted -- was the first version published to PyPI
([forge-template ADR 0036](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0036-publish-the-engine-to-pypi.md)).
`0.3.2` is the current compatible patch release. The declared range still
starts at `0.3.1`; contract tests resolve and exercise the current compatible
release without changing ProjectSpec protocol `1` or component-manifest
protocols `(1, 2)`.

The optional `engine` extra also includes `uv>=0.12,<0.13`. After a validated
render is written to adjacent staging, create-forge runs
`uv lock --directory <staging-directory>` before the atomic rename. The lock
is a client-finalisation artefact outside the engine's plan/result and follows
the [filesystem generation contract](filesystem-generation.md) under
[ADR 0021](adr/0021-client-finalises-engine-lockfiles.md).

Protocol 1 is assigned by
[forge-template ADR 0023](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0023-projectspec-protocol-v1.md).
It is now the protocol the current released `create-forge` line (v0.2.x)
supports, reachable through the `engine` extra.

[Forge-template ADR 0024](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0024-component-manifest-protocol-v1.md)
assigns component manifest protocol `1`; forge-template ADR 0031 later added
protocol `2` for the production `library`/`cli` manifests this release
consumes. Component discovery is now available behind `--engine-preview`,
not yet from the default `new` path.

[ADR 0011](adr/0011-engine-source-and-version-resolution.md), ADR 0018, and
the canonical [engine resolution contract](engine-resolution.md) define how
the range in the table above is resolved -- a bounded, install-time
dependency -- and how cross-repository development still overrides it
locally without a committed pin.

[ADR 0013](adr/0013-projectspec-construction-boundary.md) added the
ProjectSpec-building boundary (`src/create_forge/spec.py` and
`src/create_forge/engine.py`) ahead of this row being filled in; ADR 0018
fills it. `create-forge new` (the default path) still does not call it; see
the canonical [ProjectSpec construction contract](project-spec-construction.md).

The canonical [component discovery contract](component-discovery.md) adds a
second operation to that same boundary. It negotiates both the ProjectSpec
and component-manifest protocols before calling the public engine and
returns the engine's descriptors unchanged, now against the range this table
records rather than a development-only pin.

The canonical [cross-repository engine contract tests](engine-contract-tests.md)
prove that range and the public discovery, validation, and rendering
boundary, and are what a future compatible `forge-template` release must
pass before this table's range is widened.

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

The canonical
[organisation-policy protocol](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md),
[safe extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
[policy reference fixture](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
[compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
and [no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md)
close forge-template Stage 09. A downstream client applies policy before
constructing the effective ProjectSpec, uses only selected-component options
and published extension points, and consumes the top-level engine facade
without copying Foundation/component source. `create-forge` still owns
policy-source trust, explicit-choice tracking, ProjectSpec construction,
compatibility presentation, staging, and finalisation. CF-09.01
([ADR 0022](adr/0022-downstream-organisation-policy-hook.md)) delivered the
explicit-choice-tracking seam (`spec.SelectionRequest`/`SelectionProvenance`)
without adding a resolver — resolution remains a client responsibility by
design, not a gap awaiting a public resolver. Those responsibilities are
client orchestration, not a second engine implementation.
Forge-template [ADRs 0039–0042](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/README.md)
record the extension, fixture, compatibility, and no-copy decisions.

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

The canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
and [ADR 0038](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0038-organisation-policy-selection-model.md)
define component-selection policy without adding executable content.
Blueprint-style clients consume `forge-template` directly, resolve policy
before constructing the effective ProjectSpec, and preserve whether each
selection kind was explicitly supplied. They do not depend on `create-forge`
internals, and policy does not gain an arbitrary file or code-execution hook.

`create-forge` does not consume organisation policy today. CF-09.01
([ADR 0022](adr/0022-downstream-organisation-policy-hook.md)) delivered the
downstream consumption hook a policy-aware client calls into
(`pipeline.build_generation_request`'s `selection`/`provenance` keywords);
input-source trust, diagnostics, and presentation remain a client
responsibility, and the canonical policy schema and resolution semantics
remain `forge-template` contracts. See the canonical
[downstream policy-consumption contract](organisation-policy-consumption.md).

Organisations may still fork for genuinely custom executable template content.
That is distinct from the preferred downstream-client path for defaults,
required selections and forbidden selections.
