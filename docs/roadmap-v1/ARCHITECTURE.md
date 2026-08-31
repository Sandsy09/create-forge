# Forge Two-Repository Architecture

> **Implementation status:** This is the accepted target architecture under
> [ADR 0010](../adr/0010-public-engine-integration-contract.md). Strict
> [ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
> and [component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
> plus the [stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
> and [generated-project validation](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md)
> are now implemented by `forge-template`. Its `0.3.0` release contains both
> the production Library archetype and the optionless
> [CLI Application archetype](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md),
> first published to PyPI at `0.3.1`; the Stage 08 boundary review is released
> at `0.3.2`. This repository's development pin moved to
> match ([CF-08.02](https://github.com/Sandsy09/create-forge/issues/10),
> [ADR 0017](../adr/0017-cli-application-archetype-exposure.md)) and then to
> a real released range, `forge-template>=0.3.1,<0.4` as the optional
> `engine` extra alongside `uv>=0.12,<0.13` (standalone [#9](https://github.com/Sandsy09/create-forge/issues/9),
> [ADR 0018](../adr/0018-pypi-distribution-and-the-first-engine-range.md)),
> so both archetypes are discoverable and selectable behind the hidden
> `new --engine-preview` flag. `create-forge 0.2.1` finalises their lockfiles
> before atomic rename under [ADR 0021](../adr/0021-client-finalises-engine-lockfiles.md).
> The default CLI remains a thin Copier
> wrapper with a bundled registry until the coordinated cutover — a range
> assignment is not that cutover.

```text
┌─────────────────────────────┐
│        create-forge         │
│ CLI / prompts / flags       │
│ ProjectSpec construction    │
│ filesystem orchestration    │
└──────────────┬──────────────┘
               │ versioned public contract
               ▼
┌─────────────────────────────┐
│       forge-template        │
│ ProjectSpec validation      │
│ component discovery         │
│ composition / rendering     │
│ generated project content   │
└──────────────┬──────────────┘
               ▼
        Generated Project
```

The boundary lets CLI UX evolve independently from generated-project
architecture and leaves room for future clients, including Blueprint, to
consume the same engine directly. Package, protocol, trust and release rules
live in the [integration contract](../integration-contract.md).
The canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
is resolved by such a client before effective ProjectSpec construction;
ProjectSpec carries only resolved selections and applied-policy provenance.
The engine validates rendered output in memory before returning it;
`create-forge` retains filesystem staging, dynamic `uv.lock` finalisation,
atomic placement, and command execution.

## Critical invariant

Generated projects require neither `forge-template` nor `create-forge` for normal development or runtime operation. Forge is a generator, not an application framework dependency.
