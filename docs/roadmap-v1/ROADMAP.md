# Forge Foundation Two-Repository Roadmap

> **Architecture status:** [ADR 0010](../adr/0010-public-engine-integration-contract.md)
> accepts the public-engine/ProjectSpec target. Both repositories' Stage 06
> contracts are complete, the compatible engine range is released, and
> forge-template Stage 09 is complete through the canonical
> [no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md).
> The completed [two-repository Stage 09 record](roadmap/09-blueprint-compatibility/README.md)
> links forge-template ADRs 0039–0042 and create-forge
> [ADR 0024](../adr/0024-reference-client-not-framework-dependency.md).
> Create-forge #53–#55 are complete. The current
> v0.1.x Copier architecture remains
> operational until the atomic cutover. The [create-forge live issue index](github-issues/create-forge/ISSUE-INDEX.md)
> records completed baseline work and the filed dependency graph.

The roadmap remains one product roadmap, but implementation ownership is split between repository-local epics and issues.

| Stage | Theme | forge-template | create-forge | Integration intensity |
|---|---|---:|---:|---|
| 00 | Governance and Principles | 5 issues | 2 issues | High |
| 01 | Python Core | 5 issues | 2 issues | Medium |
| 02 | Developer Experience | 4 issues | 2 issues | Medium |
| 03 | Quality and CI | 6 issues | 3 issues | Medium |
| 04 | Runtime and Configuration | 5 issues | 1 issues | Medium |
| 05 | Security and Supply Chain | 5 issues | 2 issues | Medium |
| 06 | Extension and Composition Contract | 7 issues | 3 issues | High |
| 07 | Forge CLI Integration | 1 issues | 5 issues | High |
| 08 | Reference Archetype Validation | 5 issues | 3 issues | High |
| 09 | Blueprint Compatibility | 5 issues | 3 issues | High |

## Delivery rule

Create a stage epic only in repositories that have work for that stage. Where both repositories have a stage epic, link the counterpart epic as related work. Child issues stay in the repository that owns the implementation; blockers across repositories are linked explicitly.
