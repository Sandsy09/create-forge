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
([ADR 0014](adr/0014-lazy-engine-reachability.md)), which CF-07.04
([ADR 0015](adr/0015-staged-filesystem-generation.md)) completed with real
filesystem staging and finalisation -- see the canonical
[filesystem generation contract](filesystem-generation.md). The default `new`
path continues to use the bundled registry and direct-Copier integration
unchanged; the atomic cutover away from it remains a future, unfiled
decision, now that [#9](https://github.com/Sandsy09/create-forge/issues/9)
has resolved the narrower question of an installable engine range.

The `forge-template` dependency -- the optional `engine` extra since #9
([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)) --
is range-bound to `>=0.3.1,<0.4` (CF-08.02,
[ADR 0017](adr/0017-cli-application-archetype-exposure.md); ADR 0018), whose
production catalogue ships both `library` and the optionless `cli` archetype
-- real discovery now returns both descriptors. `pipeline.discover_archetypes()`
filters the result to `kind == "archetype"` for
`--engine-preview`'s `--archetype` option and interactive prompt
(`prompts.choose_archetype`); this document still covers only the adapter
`engine.discover()` itself, not that selection layer.

## Compatibility before catalogue access

`engine.discover()` performs these operations in order:

1. call the public `forge_template.get_engine_info()` facade once;
2. require the installed package version to fall within
   `create_forge.compat.SUPPORTED_ENGINE_RANGE` (`>=0.3.1,<0.4`);
3. require an overlap between the installed engine's ProjectSpec protocols and
   `create_forge.compat.SUPPORTED_PROJECTSPEC_PROTOCOLS`;
4. require an overlap between its component-manifest protocols and
   `create_forge.compat.SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS` (`(1, 2)` as
   of CF-08.02, since the `library`/`cli` manifests this pair discovers are
   protocol-2); and
5. call the public `forge_template.discover_components()` facade.

A package outside the range, or either disjoint protocol set, raises
`EngineCompatibilityError` before the engine scans its catalogue. The message
names the detected engine package version and the supported range or
detected/supported protocol sets -- checked with
`packaging.specifiers.SpecifierSet`, as distinguished by the
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

The [Data Science capability
contracts](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-capabilities.md)
provide the first production use of this boundary. The `data-science`
descriptor will require `jupyter>=1,<2`, while `scientific-python` remains an
independently optional descriptor. Stage 13 must guide users from these public
relationships without embedding either ID or rule in the CLI.

FT-11.02 implements Jupyter in the unreleased source catalogue under
[forge-template ADR
0050](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0050-production-jupyter-capability.md).
FT-11.03 implements Scientific Python under [forge-template ADR
0051](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0051-production-scientific-python-capability.md).
The current released `forge-template>=0.3.1,<0.4` range still returns only
`cli` and `library`; create-forge's discovery behaviour and compatibility
range do not change until the Stage 12 release.

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

- **CF-06.03** proves discovery, ProjectSpec validation, and fail-closed
  rendering across repositories, first against an exact development
  package/protocol pair.
- **CF-07.01** makes this adapter reachable from the shared pipeline via the
  hidden `new --engine-preview` flag (ADR 0014).
- **CF-07.04** ([ADR 0015](adr/0015-staged-filesystem-generation.md)) gives
  `--engine-preview` a real filesystem finalisation step.
- **FT-08.02** added the production Library manifest to `forge-template` at
  `0.3.0`; **FT-08.04** added the independent optionless `cli` manifest in
  the same release. **CF-08.02**
  ([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) moved this
  adapter's development pin to `0.3.0` and added the discovery-driven
  selection layer described above, so `--engine-preview` now discovers and
  chooses between both real production descriptors.
- **#9** ([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md))
  replaced that development pin with the first released, range-bound
  dependency -- `forge-template>=0.3.1,<0.4` as the optional `engine`
  extra -- so this adapter now checks a real installable range rather than
  an exact development version. The atomic cutover that replaces the
  v0.1.x registry seam and `--engine-preview` together with the engine as
  the default path remains a future, unfiled decision.
- **CF-08.03** ([ADR 0019](adr/0019-cli-archetype-parity-review.md))
  reviewed both archetypes for parity and confirmed discovery stays fully
  engine-owned -- descriptors pass through this adapter unchanged, and
  `pipeline._resolved_component_options` now gates its one derivation on a
  discovered descriptor's declared options rather than a hardcoded archetype
  id.

## Executable examples

[`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py) covers the
real production catalogue, unmodified archetype/capability/platform
descriptors, both protocol mismatches before catalogue access, and structured
discovery failure propagation. The engine import boundary remains enforced by
[`tests/test_engine_contract.py`](../tests/test_engine_contract.py).
The exact installed/sibling pair and public rendering boundary are covered by
[`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py).
`pipeline.discover_archetypes()`'s `kind`-filtering and the `--archetype`
selection surface are covered by
[`tests/test_pipeline.py`](../tests/test_pipeline.py) and
[`tests/test_cli.py`](../tests/test_cli.py).

When discovery behaviour changes, update this contract and its executable
examples in the same pull request.
