# Repository Ownership and Integration Model

> **Implementation status:** The ProjectSpec/public-engine ownership below is
> accepted by [ADR 0010](../adr/0010-public-engine-integration-contract.md)
> but is not current repository behaviour. The v0.1.x Copier/registry
> ownership remains operational until the coordinated cutover.

The [canonical Forge architectural terminology](https://github.com/Sandsy09/forge-template/blob/main/docs/terminology.md)
defines the component kinds and selection inputs referenced here. The
[Foundation guarantees](https://github.com/Sandsy09/forge-template/blob/main/docs/foundation-guarantees.md)
and [Foundation scope](https://github.com/Sandsy09/forge-template/blob/main/docs/foundation-scope.md)
define the mandatory outcomes and concern-level boundary that this ownership
model must preserve. The
[Python support policy](https://github.com/Sandsy09/forge-template/blob/main/docs/python-support.md)
defines generated-project interpreter choices, defaults, and lifecycle in the
repository that owns those outputs. The
[editor integration strategy](https://github.com/Sandsy09/forge-template/blob/main/docs/editor-integration.md)
assigns future editor-specific bridges to optional `forge-template`
capabilities and keeps canonical validation independent of editor state.
The [configuration ownership conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/configuration-ownership.md)
assign generated runtime settings to their owning archetype or capability;
`create-forge` presents inputs but does not own or duplicate those schemas.
The [environment-variable conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/environment-variables.md)
define generated runtime names, precedence, examples, and local dotenv
behaviour. The existing `FORGE_*` variables remain create-forge's own CLI
configuration interface and are not generated-project runtime inputs.
The [structured logging capability](https://github.com/Sandsy09/forge-template/blob/main/docs/structured-logging.md)
defines generated runtime event ownership, process configuration, formatting,
redaction, and platform-exporter boundaries. It does not govern create-forge's
own CLI diagnostics or user-facing error presentation.
The [path and resource ownership conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/paths-and-resources.md)
and [exception ownership conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/exception-ownership.md)
keep those generated runtime concerns with the contributing archetype or
capability. They do not define create-forge's filesystem orchestration or CLI
error presentation.

## `forge-template`

Owns **what a generated project is** and **how it is composed**.

It owns:

- Foundation and archetype templates;
- capability and platform components;
- optional editor capabilities and their project-scoped contributions;
- profile and organisation-policy selection inputs;
- component manifests and compatibility metadata;
- the canonical ProjectSpec input contract;
- template variables and validation;
- generated-project Python support choices, defaults, and lifecycle;
- owner-local generated-project runtime configuration and environment-input
  conventions;
- owner-local generated-project structured-logging conventions and capability
  contributions;
- owner-local generated-project path, resource, and exception conventions;
- composition, merge/conflict and override rules;
- rendering/generation logic;
- structured engine errors and generated-project validation;
- deterministic generation tests.

It does **not** own interactive prompts, command-line parsing, terminal output or target-directory UX.

## `create-forge`

Owns **how a user describes and requests a project**.

It owns:

- CLI commands and flags;
- interactive prompts;
- user-facing validation and error presentation;
- construction of the canonical ProjectSpec;
- component discovery for CLI choices via the forge-template API;
- filesystem orchestration and safe target handling;
- CLI diagnostics/version reporting;
- end-to-end scaffolding tests.

It does **not** own copies of templates, a second component catalogue, Python
support or editor-integration defaults, generated runtime configuration
schemas, environment-variable, structured-logging, path/resource, or exception
contracts, compatibility rules, or rendering/composition logic.

## Dependency direction

```text
User
  ↓
create-forge
  ↓  ProjectSpec / public engine API
forge-template
  ↓
Generated repository
```

The dependency is one-way: `create-forge` consumes `forge-template`.
`forge-template` must not import or depend on `create-forge`. Compatibility,
source trust and release sequencing are defined by the
[integration contract](../integration-contract.md).

## Cross-repository issue rule

If an issue is blocked by the other repository, link that external issue under **Cross-repository dependencies**. Do not create a second ticket that implements the same responsibility in both repositories.
