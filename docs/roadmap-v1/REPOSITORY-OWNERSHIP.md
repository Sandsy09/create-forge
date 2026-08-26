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
support or editor-integration defaults, compatibility rules, or
rendering/composition logic.

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
