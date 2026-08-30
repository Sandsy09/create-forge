# Stage 06 — Extension and Composition Contract

## Repository ownership

### forge-template

- [x] [**FT-06.01 — Design ProjectSpec schema**](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md) —
  protocol v1 is complete under
  [forge-template ADR 0023](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0023-projectspec-protocol-v1.md).
- [x] [**FT-06.02 — Define component manifest format**](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md) —
  strict TOML protocol v1 is complete under
  [forge-template ADR 0024](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0024-component-manifest-protocol-v1.md).
- [x] [**FT-06.03 — Define deterministic composition order**](https://github.com/Sandsy09/forge-template/blob/main/docs/composition-order.md) —
  complete under [forge-template ADR 0025](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0025-deterministic-composition-order.md).
- [x] [**FT-06.04 — Define file conflict and override rules**](https://github.com/Sandsy09/forge-template/blob/main/docs/file-conflicts.md) —
  complete under [forge-template ADR 0026](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0026-file-conflict-and-override-rules.md).
- [x] [**FT-06.05 — Design template variable contract**](https://github.com/Sandsy09/forge-template/blob/main/docs/template-variables.md) —
  complete under [forge-template ADR 0027](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0027-template-variable-contract.md).
- [x] [**FT-06.06 — Create composition contract tests**](https://github.com/Sandsy09/forge-template/blob/main/docs/composition-fixtures.md) —
  complete under [forge-template ADR 0028](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0028-composition-contract-fixtures.md).
- [x] [**FT-06.07 — Expose stable template-engine API**](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md) —
  the `0.2.x` public facade is complete under
  [forge-template ADR 0029](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0029-stable-template-engine-api.md),
  with an empty production catalogue on that compatibility line; Library
  arrived later on `forge-template/main` at `0.3.0`.

The counterpart [forge-template epic #15](https://github.com/Sandsy09/forge-template/issues/15)
is complete. The `create-forge` Stage 06 development contract is also complete:
the released engine range remains unassigned and ProjectSpec protocol 1 remains
unsupported by released CLI lines until the later atomic cutover.

### create-forge

- Epic: [CF-EPIC-06 / #37](https://github.com/Sandsy09/create-forge/issues/37)
- [x] [**CF-06.01 — Implement canonical ProjectSpec builder**](https://github.com/Sandsy09/create-forge/issues/46)
  ([ADR 0013](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0013-projectspec-construction-boundary.md),
  [canonical ProjectSpec construction contract](https://github.com/Sandsy09/create-forge/blob/main/docs/project-spec-construction.md))
- [x] [**CF-06.02 — Implement component discovery adapter**](https://github.com/Sandsy09/create-forge/issues/47)
  ([canonical component discovery contract](https://github.com/Sandsy09/create-forge/blob/main/docs/component-discovery.md))
- [x] [**CF-06.03 — Add cross-repository contract tests**](https://github.com/Sandsy09/create-forge/issues/48)
  ([canonical cross-repository engine contract tests](https://github.com/Sandsy09/create-forge/blob/main/docs/engine-contract-tests.md))

## Stage record

CF-06.01 builds the create-forge-owned half of ProjectSpec construction ahead
of any command using it: `src/create_forge/spec.py` maps CLI answers to the
ProjectSpec wire payload and validates nothing; `src/create_forge/engine.py`
is the one module that imports `forge_template`, negotiating the ProjectSpec
protocol and calling the engine's own parsing and catalogue validation. The
engine is a development-only dependency pinned to a commit — `forge-template`
`0.2.0` has no PEP 440 tag yet — so no engine range is assigned and
`create-forge new` is unchanged. Catalogue validation is proven to fail
closed against `forge-template`'s intentionally empty `0.2.0` production
catalogue; that characterisation remains correct for the fixed development
pair even though Stage 08 has since added Library to `forge-template/main` at
`0.3.0`. CF-06.02 adds `engine.discover()`, which checks both
ProjectSpec and component-manifest protocol compatibility before returning the
engine's immutable descriptors unchanged. It deliberately has no registry
fallback and remains unreachable from the CLI until CF-07.01. CF-06.03 pins
and proves exact development pair `forge-template==0.2.0`, ProjectSpec
protocol `1`, and component-manifest protocol `1`; package and protocol
mismatches fail before public engine operations. Its render adapter is
in-memory and currently fails closed against the intentionally empty catalogue,
while forge-template's golden suite remains the successful rendering proof.
No released engine range or CLI behavior changes in this completed stage.

## Stage completion rule

- [x] Repo-local issues are complete or explicitly deferred.
- [x] Cross-repository blockers are resolved.
- [x] Public contracts changed by this stage are documented/versioned.
- [x] No implementation concern is duplicated across repositories.
