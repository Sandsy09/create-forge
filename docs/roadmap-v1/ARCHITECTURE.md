# Forge Two-Repository Architecture

> **Implementation status:** This is the accepted target architecture under
> [ADR 0010](../adr/0010-public-engine-integration-contract.md). Strict
> [ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
> and [component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
> plus the [stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
> and [generated-project validation](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md)
> are now implemented by `forge-template`. Its production catalogue is empty,
> and CLI integration is not the current implementation. The released v0.1.x
> CLI remains a thin Copier wrapper with a bundled registry until the
> coordinated cutover.

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
The engine validates rendered output in memory before returning it;
`create-forge` retains filesystem staging, finalisation, and command execution.

## Critical invariant

Generated projects require neither `forge-template` nor `create-forge` for normal development or runtime operation. Forge is a generator, not an application framework dependency.
