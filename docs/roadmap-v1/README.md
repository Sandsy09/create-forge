# Forge Foundation Roadmap Pack — Two-Repository Edition

This revision models Forge as two independent repositories that work together through an explicit contract:

- **`forge-template`** owns generated content, component metadata and the template/composition engine.
- **`create-forge`** owns the CLI experience, input collection and orchestration of that engine.

The [canonical Forge architectural terminology](https://github.com/Sandsy09/forge-template/blob/main/docs/terminology.md)
defines the ecosystem, composition, and authority terms used by both
repositories. The [Foundation guarantees](https://github.com/Sandsy09/forge-template/blob/main/docs/foundation-guarantees.md)
define the mandatory generated-project outcomes, while the
[Foundation scope](https://github.com/Sandsy09/forge-template/blob/main/docs/foundation-scope.md)
defines which concerns may belong in that baseline. The
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
defines the first production archetype, implemented on
`forge-template/main`, released at `0.3.0`, and included in the completed
two-archetype [composition review](https://github.com/Sandsy09/forge-template/blob/main/docs/composition-architecture-review.md)
released at `0.3.2`. The
[CLI Application archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
selects the engine-owned, optionless `cli` archetype and derives its command
from `ProjectSpec.project.repository_name`; FT-08.04 implemented it, and
CF-08.02 exposes both archetypes behind `create-forge`'s hidden
`--engine-preview` flag. Neither contract changes this repository's default
`new` path. `create-forge 0.2.1` keeps the released engine range unchanged and
adds client-owned lock finalisation under
[ADR 0021](../adr/0021-client-finalises-engine-lockfiles.md). The
[Python support policy](https://github.com/Sandsy09/forge-template/blob/main/docs/python-support.md)
defines the generated-project CPython window, defaults, and release lifecycle.
The [editor integration strategy](https://github.com/Sandsy09/forge-template/blob/main/docs/editor-integration.md)
keeps Foundation and Forge's default profile editor-neutral while defining the
boundary for future optional editor capabilities.
The [configuration ownership conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/configuration-ownership.md)
keep generated runtime settings with their owning archetype or capability and
require explicit entrypoint assembly and injection.
The [environment-variable conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/environment-variables.md)
define owner-prefixed generated runtime inputs, source precedence, and
explicit local dotenv behaviour. They do not govern create-forge's own
CLI-local `FORGE_*` configuration variables.
The [structured logging capability](https://github.com/Sandsy09/forge-template/blob/main/docs/structured-logging.md)
defines owner-local generated runtime events, one entrypoint-owned process
configuration, the portable event envelope, and redaction boundaries.
It does not change create-forge's CLI diagnostics or error presentation.
The [path and resource ownership conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/paths-and-resources.md)
and [exception ownership conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/exception-ownership.md)
complete the owner-local generated runtime boundary without adding Foundation
path helpers or a universal exception hierarchy.
The [GitHub Action pinning policy](https://github.com/Sandsy09/forge-template/blob/main/docs/github-action-pinning.md)
requires immutable remote workflow references for automation owned or generated
by `forge-template`. It does not govern `create-forge`'s repository-local
workflows, which remain independently owned and unchanged.
The canonical
[ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
defines the strict effective generation request owned by `forge-template`.
`create-forge` retains construction and user-facing orchestration. The canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
defines how downstream clients resolve component-selection policy before
constructing that effective request. CF-09.01
([ADR 0022](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0022-downstream-organisation-policy-hook.md))
delivered the client hook; `create-forge` still consumes no policy itself.
Forge-template Epic 09 is complete through its canonical
[extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
[policy fixture](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
[compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
and [no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md).
Forge-template [ADRs 0039–0042](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/README.md)
record those four decisions.
Create-forge Epic #40 and #53–#55 remain open for the client-owned half.
The canonical
[component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
defines engine-owned bundled component metadata and compatibility. The
[stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
now exposes typed discovery, validation, planning, in-memory rendering, and
structured errors under
[ADR 0029](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0029-stable-template-engine-api.md).
The canonical
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md)
and [ADR 0030](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0030-generated-project-validation.md)
complete the `forge-template` side of Stage 07 by validating rendered output
in memory. Stage 07 and Stage 08 are now complete across both repositories;
the default Copier-to-engine cutover remains separate future work.
This roadmap links to the canonical sources rather than maintaining second
definitions.

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
