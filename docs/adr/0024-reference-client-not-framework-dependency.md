# 24. Keep create-forge a reference client, not a framework dependency

## Status

Accepted

## Context

[Issue #55 / CF-09.03](https://github.com/Sandsy09/create-forge/issues/55)
closes the create-forge half of Stage 09. Its question is whether the
organisation-policy and downstream-client work delivered by
[ADR 0022](0022-downstream-organisation-policy-hook.md) and
[ADR 0023](0023-downstream-client-reference.md) preserved the dependency
direction accepted by [ADR 0010](0010-public-engine-integration-contract.md),
or quietly turned `create-forge` into a framework other clients must reuse.

The cross-repository prerequisites are complete. Forge-template's
[no-copy inheritance proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md)
shows that a policy-aware client can use the production catalogue through the
top-level public facade without copying Foundation or component source. The
independent client in `examples/downstream_cli.py` proves the same boundary
from this repository: it imports no `create_forge` module, carries its own
compatibility bounds and policy resolver, and produces a project containing
no dependency on either Forge package.

The remaining risk is architectural drift. A future convenience helper could
be added to `create-forge` and then imported by a second client, the engine
could acquire a reverse dependency, or generated projects could begin to
require their generator during normal development. Any of those changes
would make the dependency graph cyclic or turn a generator into an
application framework.

## Decision

`create-forge` is one reference client of the versioned `forge-template`
engine. It is not a reusable client framework. A Blueprint-style client
builds its own CLI on the same top-level `forge_template` facade and does not
import `create_forge`.

The engine owns logic that must behave identically for every client:
ProjectSpec and component-manifest protocols, compatibility facts, discovery,
schema and selection validation, planning, composition, rendering, generated
content, and rendered-project validation. If multiple clients need new logic
in one of those areas, it must be accepted and published through a supported
`forge-template` API rather than copied between clients or exported from
`create-forge`.

Each client owns its interaction and orchestration policy: commands, prompts,
policy-source discovery and trust, policy parsing and resolution until a
public resolver is separately accepted, explicit-choice tracking, effective
ProjectSpec construction, its own package bounds and unsupported-version
presentation, destination handling, finalisation, and cleanup. Similar
client-owned implementations are independent clients, not shared engine logic.

Organisation policy remains selection-only. It may influence resolved
component identifiers and record applied policy identifiers; it cannot carry
files, template content, component options, rendering code, arbitrary
overlays, plugin roots, or executable hooks. Forge-template's private fixture
catalogues remain test seams and are not client extension mechanisms.

The dependency direction is strict:

```text
downstream client (including create-forge)
  -> forge-template public facade
  -> generated project
```

`forge-template` must neither declare nor import `create-forge`. Other clients
must not depend on `create-forge`, and generated projects must depend on
neither Forge distribution for building, development, testing, or runtime.

## Consequences

- The living [integration contract](../integration-contract.md) records the
  ownership boundary and the evidence that enforces it.
- The independent downstream example remains repository-only and outside the
  `create-forge` wheel and sdist; it demonstrates a client rather than adding
  a public framework surface.
- Tests inspect the supported installed engine's metadata and imports for a
  reverse `create-forge` dependency. Existing AST guards continue to require
  both clients to use only the top-level engine facade.
- Engine-path end-to-end tests verify that both production archetypes have no
  Forge package in generated build, development, test, optional, or runtime
  dependencies or in `uv.lock`.
- A future public organisation-policy resolver, component distribution
  mechanism, or other shared-client service requires its own contract and ADR;
  it cannot be inferred from test fixtures or this decision.
- No production Python API, CLI behavior, template, or forge-template source
  changes result from this decision.
