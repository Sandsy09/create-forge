# Component Discovery

This is the living contributor contract for how `create-forge` discovers the
components shipped by the `forge-template` engine. The canonical manifest
schema and discovery semantics remain owned by
[`forge-template`](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md);
this document defines only the client adapter and its compatibility boundary.

## Status

`src/create_forge/engine.py` exposes a tested `discover()` adapter, but no
shipped command calls it yet. The released v0.1.x CLI continues to use its
bundled registry and direct-Copier path until the atomic cutover in CF-07.01.

The development-only `forge-template` 0.2.0 dependency currently has an empty
production catalogue, so real discovery returns `()`. That is expected until
Stage 08 migrates the first production archetype; an empty result is not a
reason to fall back to `templates.toml`.

## Compatibility before catalogue access

`engine.discover()` performs these operations in order:

1. call the public `forge_template.get_engine_info()` facade once;
2. require an overlap between the installed engine's ProjectSpec protocols and
   `create_forge.engine.SUPPORTED_PROJECTSPEC_PROTOCOLS`;
3. require an overlap between its component-manifest protocols and
   `create_forge.engine.SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS`; and
4. call the public `forge_template.discover_components()` facade.

Either disjoint protocol set raises `EngineCompatibilityError` before the
engine scans its catalogue. The message names the detected engine package
version and the detected and supported protocol sets. No engine package range
is checked yet: the dependency remains a development-only commit pin, and
CF-06.03 owns assigning and testing the first bounded package/protocol pair.

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

- **CF-06.03** proves discovery, ProjectSpec validation, rendering, and the
  exact supported package/protocol pair across repositories.
- **CF-07.01** makes this adapter reachable from the shared `new` pipeline and
  replaces the v0.1.x registry seam atomically.
- **Stage 08** adds production manifests, after which real discovery will
  return the Library and later archetype descriptors.

## Executable examples

[`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py) covers the
real empty catalogue, unmodified archetype/capability/platform descriptors,
both protocol mismatches before catalogue access, and structured discovery
failure propagation. The engine import boundary remains enforced by
[`tests/test_engine_contract.py`](../tests/test_engine_contract.py).

When discovery behaviour changes, update this contract and its executable
examples in the same pull request.
