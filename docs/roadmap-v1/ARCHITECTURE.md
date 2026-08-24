# Forge Two-Repository Architecture

> **Planning status:** This is a proposed target architecture imported by the
> roadmap, not the current accepted implementation. The current CLI is a thin
> Copier wrapper with a bundled registry. [CF-00.02 / #41](https://github.com/Sandsy09/create-forge/issues/41)
> decides whether this model supersedes or is reframed around the accepted ADRs.

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

The boundary lets CLI UX evolve independently from generated-project architecture and leaves room for future clients, including Blueprint, to consume the same engine directly.

## Critical invariant

Generated projects require neither `forge-template` nor `create-forge` for normal development or runtime operation. Forge is a generator, not an application framework dependency.
