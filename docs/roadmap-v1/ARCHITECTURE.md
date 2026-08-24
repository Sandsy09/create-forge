# Forge Two-Repository Architecture

> **Implementation status:** This is the accepted target architecture under
> [ADR 0010](../adr/0010-public-engine-integration-contract.md), but it is
> not the current implementation. The released v0.1.x CLI remains a thin
> Copier wrapper with a bundled registry until the coordinated cutover.

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

## Critical invariant

Generated projects require neither `forge-template` nor `create-forge` for normal development or runtime operation. Forge is a generator, not an application framework dependency.
