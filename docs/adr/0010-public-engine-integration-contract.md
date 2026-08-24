# 10. Adopt the forge-template public engine contract

## Status

Accepted

## Context

The released `create-forge` v0.1.x line is a thin Copier client. It bundles a
template registry, owns the prompt catalogue, and calls Copier's Python API
directly. That design is small and proven, but it cannot provide one canonical
ProjectSpec, discover composable components without duplicating metadata, or
let another client such as Blueprint reuse the same validation and rendering
contract.

The Forge Foundation roadmap instead assigns ProjectSpec validation,
component metadata, compatibility rules, composition, and rendering to
`forge-template`. The CLI would translate user input into that contract and
orchestrate safe output handling. Adopting that target changes the integration
and trust boundaries recorded by ADRs 0004–0006 and the organisation model in
ADR 0008, so it needs an explicit decision before either repository implements
the Stage 04–09 work.

## Decision

Adopt a versioned public engine owned by `forge-template` as Forge's long-term
integration contract. `create-forge` will be the reference CLI client of that
engine, not a second owner of template or composition behaviour.

The ownership boundary is:

| Responsibility | Owner |
| --- | --- |
| CLI commands, flags, prompts, user-facing errors and diagnostics | `create-forge` |
| Construction of ProjectSpec from interactive and non-interactive input | `create-forge` |
| Filesystem staging, target conflict handling and finalisation | `create-forge` |
| ProjectSpec types, validation and structured engine errors | `forge-template` |
| Component metadata, discovery and compatibility rules | `forge-template` |
| Composition, rendering, Copier integration and generated content | `forge-template` |

The dependency direction is strictly `create-forge` to `forge-template`.
`forge-template` must not import `create-forge`, and a generated project must
need neither package for normal development, testing, building or runtime
operation.

A `forge-template` release will be one installable unit containing the public
engine and the reviewed template assets it executes. The package version and
the serialised ProjectSpec protocol are separate compatibility axes:

- Before 1.0, `create-forge` must bound a supported engine dependency to one
  minor line. From 1.0 onward, it must bound it to one major line. Every range
  has both a lower and an upper bound.
- ProjectSpec carries an explicit protocol version. Breaking wire-format,
  validation or semantic changes increment it; backward-compatible additions
  may remain on the same version.
- The first concrete engine range and protocol number will be assigned when
  CF-04.01 and the Stage 06 schema define real interfaces. This decision sets
  the compatibility rules without reserving versions for APIs that do not yet
  exist.
- An unsupported engine or protocol must fail before component discovery,
  rendering, template tasks or destination writes. The error identifies the
  detected and supported versions and gives a remediation. There is no silent
  fallback to the bundled registry or direct Copier.

Normal discovery is limited to component metadata and template assets shipped
by the installed, version-constrained `forge-template` release. Runtime remote
registries and arbitrary component plugins are not accepted. Cross-repository
development may use an explicit, warned local or VCS engine source, but the
override must implement a supported public contract and must never be selected
silently from ordinary user configuration.

At the engine cutover, that compatible source override replaces the current
arbitrary `--template-url` escape hatch. The new architecture will not retain a
second direct-Copier adapter for unrelated templates. Until the cutover, the
v0.1.x implementation and its existing warning remain unchanged.

The migration will be atomic rather than a dual-path deprecation period:

1. `forge-template` releases the engine, reviewed assets and compatibility
   metadata first.
2. Cross-repository contract and end-to-end tests prove the exact supported
   pair, including existing generated-project update behaviour.
3. `create-forge` releases with the bounded engine dependency and removes its
   direct Copier/registry path in the same pre-1.0 compatibility-line change.
4. Earlier `create-forge` releases remain pinned to their earlier behaviour.

A breaking engine change starts a new compatibility line and, when required,
a new ProjectSpec protocol. It is released before the `create-forge` version
that adopts it, with explicit compatibility and migration notes. Existing
generated projects must retain a supported update path or receive an explicit,
tested migration before any cutover release.

For organisations, downstream clients and policy integrations should consume
the engine directly rather than import or fork `create-forge` internals.
Forking remains a supported route for genuinely custom executable template
content that lies outside the reviewed public distribution.

This decision supersedes ADRs 0004, 0005, 0006 and 0008 for the target
architecture. Their current operational rules remain authoritative until the
atomic cutover. In particular, ADR 0005's trust principle is retained: code is
executed by default only when it shipped in the reviewed release. Copier and
`unsafe=True` move behind the engine boundary instead of disappearing as a
security concern.

The rejected long-term alternative is to preserve the thin Copier client and
bundled registry. It remains appropriate for v0.1.x, but it would require each
client to recreate ProjectSpec validation, component discovery and
compatibility behaviour, preventing a single reusable contract for
`create-forge`, Blueprint and future clients.

## Consequences

- This ADR changes the accepted target, not the current Python implementation
  or public CLI. The v0.1.x invariants remain in force until later roadmap
  issues implement the cutover.
- `forge-template` must become an installable, versioned engine distribution;
  the exact normal package source and override interface remain CF-04.01 work.
- `create-forge` will eventually stop owning `templates.toml`, the Copier API
  call site and arbitrary Copier-template execution.
- Compatibility checks and structured errors become mandatory before any
  side effect, and diagnostics must expose enough package, protocol, template
  and CLI version information to reproduce a failure.
- A coordinated breaking release is more deliberate than independent changes,
  but bounded dependencies keep older clients working while a new line is
  prepared.
- Organisation policy can evolve outside the reference CLI without turning
  `create-forge` into a framework dependency or weakening the reviewed-source
  trust boundary.
