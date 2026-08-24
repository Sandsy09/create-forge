# Forge Foundation Roadmap Pack — Two-Repository Edition

This revision models Forge as two independent repositories that work together through an explicit contract:

- **`forge-template`** owns generated content, component metadata and the template/composition engine.
- **`create-forge`** owns the CLI experience, input collection and orchestration of that engine.

The [canonical Forge architectural terminology](https://github.com/Sandsy09/forge-template/blob/main/docs/terminology.md)
defines the ecosystem, composition, and authority terms used by both
repositories. The [Foundation guarantees](https://github.com/Sandsy09/forge-template/blob/main/docs/foundation-guarantees.md)
define the mandatory generated-project outcomes, while the
[Foundation scope](https://github.com/Sandsy09/forge-template/blob/main/docs/foundation-scope.md)
defines which concerns may belong in that baseline. This roadmap links to the
canonical sources rather than maintaining second definitions.

Start with `REPOSITORY-OWNERSHIP.md`, then `ROADMAP.md`, then the
repo-specific GitHub issue indexes.

The `create-forge` issue drafts have been filed and pruned. Its
`ISSUE-INDEX.md` links the live GitHub issues and records work completed before
the roadmap was imported; GitHub issue bodies are the source of truth for open
work.

## Structure

```text
forge-foundation-roadmap-pack-v2/
├── README.md
├── REPOSITORY-OWNERSHIP.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── roadmap/<stage>/README.md
└── github-issues/
    ├── GITHUB-SETUP.md
    ├── CROSS-REPO-DEPENDENCIES.md
    └── create-forge/ISSUE-INDEX.md
```

Each repository receives its own epics and child issues. Cross-repository work
is referenced as a dependency instead of being duplicated.
