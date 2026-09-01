# Stage 09 — Blueprint Compatibility

## Repository ownership

### forge-template

- [x] **FT-09.01 — Define organisation policy model** — completed by the
  canonical [organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md),
  [ADR 0038](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0038-organisation-policy-selection-model.md),
  and [forge-template PR #89](https://github.com/Sandsy09/forge-template/pull/89).
- [x] **FT-09.02 — Define safe override and extension points** — completed by
  the canonical [extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
  [ADR 0039](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0039-deny-policy-file-overrides.md),
  and [forge-template PR #90](https://github.com/Sandsy09/forge-template/pull/90).
- [x] **FT-09.03 — Create generic downstream policy reference fixture** —
  completed by the canonical [fixture guide](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
  [ADR 0040](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0040-organisation-policy-reference-fixture.md),
  and [forge-template PR #91](https://github.com/Sandsy09/forge-template/pull/91).
- [x] **FT-09.04 — Define Forge-Blueprint compatibility policy** — completed
  by the canonical [compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
  [ADR 0041](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0041-forge-blueprint-compatibility-policy.md),
  and [forge-template PR #92](https://github.com/Sandsy09/forge-template/pull/92).
- [x] **FT-09.05 — Validate no-copy inheritance model** — completed by the
  canonical [no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md),
  [ADR 0042](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0042-validate-no-copy-downstream-inheritance.md),
  and [forge-template PR #93](https://github.com/Sandsy09/forge-template/pull/93).

Forge-template [Epic #18](https://github.com/Sandsy09/forge-template/issues/18)
and its milestone are complete. Its contracts keep policy selection-only,
deny arbitrary file replacement, define compatibility, and prove public-
facade reuse without copied Foundation/component source. The private fixture
catalogue remains a forge-template test seam, not a client plugin mechanism.

### create-forge

- Epic: [CF-EPIC-09 / #40](https://github.com/Sandsy09/create-forge/issues/40)
- [x] [**CF-09.01 — Define downstream policy-consumption hook**](https://github.com/Sandsy09/create-forge/issues/53)
  — complete. `pipeline.build_generation_request` accepts a `selection`/
  `provenance` pair built from `spec.SelectionRequest`/`SelectionProvenance`;
  `create-forge` ships no resolver and reads no policy document by design.
  See [ADR 0022](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0022-downstream-organisation-policy-hook.md)
  and the canonical [downstream policy-consumption contract](https://github.com/Sandsy09/create-forge/blob/main/docs/organisation-policy-consumption.md).
- [x] [**CF-09.02 — Create downstream CLI integration reference**](https://github.com/Sandsy09/create-forge/issues/54)
  — complete. `examples/downstream_cli.py`: a second, independent
  Blueprint-style CLI over the public `forge_template` facade, with its own
  compatibility bounds and its own minimal organisation-policy resolver, and
  no dependency on `create-forge` at all (an AST guard proves it). See
  [ADR 0023](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0023-downstream-client-reference.md)
  and the canonical [downstream client reference](https://github.com/Sandsy09/create-forge/blob/main/docs/downstream-client-reference.md).
- [x] [**CF-09.03 — Validate create-forge is a reference client, not a framework dependency**](https://github.com/Sandsy09/create-forge/issues/55)
  — complete. [ADR 0024](../../../adr/0024-reference-client-not-framework-dependency.md)
  records the strict one-way dependency, the living
  [integration contract](../../../integration-contract.md) maps every
  acceptance criterion to executable evidence, and both production
  archetypes are checked for Forge-free generated dependencies and locks.

## Stage completion rule

- [x] Repo-local issues are complete or explicitly deferred.
- [x] Cross-repository blockers are resolved.
- [x] Public contracts changed by this stage are documented/versioned.
- [x] No implementation concern is duplicated across repositories.
