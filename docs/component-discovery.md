# Component Discovery

This is the living contributor contract for how `create-forge` discovers the
components shipped by the `forge-template` engine. The canonical manifest
schema and discovery semantics remain owned by
[`forge-template`](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md);
this document defines only the client adapter and its compatibility boundary.

## Status

`src/create_forge/engine.py` exposes a tested `discover()` adapter, called
by the shared pipeline (`src/create_forge/pipeline.py`) as of CF-07.01 --
reachable today only via the hidden `new --engine-preview` flag
([ADR 0014](adr/0014-lazy-engine-reachability.md)). The default `new` path
continues to use the bundled registry and direct-Copier integration
unchanged; the atomic cutover away from it remains blocked on
[#9](https://github.com/Sandsy09/create-forge/issues/9) and CF-07.04.

The development-only `forge-template` 0.2.0 dependency currently has an empty
production catalogue, so real discovery returns `()`. That is expected until
Stage 08 migrates the first production archetype; an empty result is not a
reason to fall back to `templates.toml`.

## Compatibility before catalogue access

`engine.discover()` performs these operations in order:

1. call the public `forge_template.get_engine_info()` facade once;
2. require exact development package version `0.2.0`;
3. require an overlap between the installed engine's ProjectSpec protocols and
   `create_forge.engine.SUPPORTED_PROJECTSPEC_PROTOCOLS`;
4. require an overlap between its component-manifest protocols and
   `create_forge.engine.SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS`; and
5. call the public `forge_template.discover_components()` facade.

An untested package or either disjoint protocol set raises
`EngineCompatibilityError` before the engine scans its catalogue. The message
names the detected engine package version and the exact development version or
detected/supported protocol sets. No released engine range is checked: the
dependency remains a development-only commit pin, as distinguished by the
[cross-repository engine contract tests](engine-contract-tests.md).

## Descriptor ownership

The adapter returns the engine's immutable `ComponentDescriptor` tuple
unchanged and in engine-defined order. It does not recreate the descriptor
schema or translate it into registry models.

- `id` is the canonical ProjectSpec, persistence, relationship, and option
  namespace value.
- `name` and `description` are presentation metadata; future prompts may show
  them without treating display text as identity.
- `kind` partitions descriptors into archetypes, capabilities, and platforms.
- `projectspec_protocols` and `requires_python` remain engine-owned
  compatibility metadata.
- `requires`, `conflicts`, and `options` are preserved for client guidance.

Discovery is not selection validation. `create-forge` must not silently add a
required component, remove a conflict, decide Python compatibility, or copy an
option rule into its own schema. It builds an explicit ProjectSpec and calls
`forge_template.validate_project_spec`; that engine result remains
authoritative.

## Failures and trust boundary

Expected catalogue failures remain structured `ForgeEngineError` values from
the public engine. The adapter propagates them without substituting the bundled
registry, direct Copier, a remote registry, an entry point, a plugin, or an
arbitrary component directory.

Normal discovery is therefore limited to reviewed metadata and assets shipped
inside the installed `forge-template` distribution. The facade exposes no
filesystem or package-resource paths, and `create-forge` must not reach into
engine internals to obtain them.

## What changes next

- **CF-06.03** proves discovery, ProjectSpec validation, fail-closed rendering,
  and the exact development package/protocol pair across repositories.
- **CF-07.01** makes this adapter reachable from the shared pipeline via the
  hidden `new --engine-preview` flag (ADR 0014). Selection stays
  caller-supplied (`archetype=template.id`, no capabilities/platforms) --
  discovery runs for real but does not yet drive it.
- **CF-07.04**, once [#9](https://github.com/Sandsy09/create-forge/issues/9)
  resolves a distribution channel, performs the atomic cutover that replaces
  the v0.1.x registry seam and `--engine-preview` together.
- **Stage 08** adds production manifests, after which real discovery will
  return the Library and later archetype descriptors.

## Executable examples

[`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py) covers the
real empty catalogue, unmodified archetype/capability/platform descriptors,
both protocol mismatches before catalogue access, and structured discovery
failure propagation. The engine import boundary remains enforced by
[`tests/test_engine_contract.py`](../tests/test_engine_contract.py).
The exact installed/sibling pair and public rendering boundary are covered by
[`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py).

When discovery behaviour changes, update this contract and its executable
examples in the same pull request.
