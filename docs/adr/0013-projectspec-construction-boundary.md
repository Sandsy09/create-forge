# 13. Build ProjectSpec as a wire payload behind a single engine adapter

## Status

Accepted

## Context

[CF-06.01](https://github.com/Sandsy09/create-forge/issues/46) is the first
child of [CF-EPIC-06](https://github.com/Sandsy09/create-forge/issues/37),
unblocked by `forge-template` completing FT-06.01 through FT-06.07: a
strict, immutable ProjectSpec protocol
([`forge_template.project_spec`](https://github.com/Sandsy09/forge-template/blob/main/src/forge_template/project_spec.py)),
and a stable, side-effect-free engine facade
([`template-engine-api.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md))
exposing `get_engine_info`, `parse_project_spec`, `validate_project_spec`,
`discover_components`, `plan_generation`, and `render_project` behind one
public exception, `ForgeEngineError`.

Three facts about the sibling repository shape this decision.

`forge-template` `0.2.0` is unreleased: its `pyproject.toml` declares that
version, but the only published tags are `v0.1.0` and `v0.1.1`, and it still
carries `Private :: Do Not Upload`. It cannot become a runtime dependency
yet — a direct git reference cannot express the bounded lower/upper range
[the integration contract](../integration-contract.md#version-and-protocol-compatibility)
requires, and [ADR 0011](0011-engine-source-and-version-resolution.md) is
explicit that `create-forge` must keep its engine range unassigned until an
adapter and cross-repository contract tests exist and pass.

The production component catalogue is intentionally empty
(`src/forge_template/components/` holds no manifests). `ComponentSelection`
requires exactly one `archetype`, and `validate_manifest_selection` rejects
any value against an empty catalogue. `forge-template`'s own documentation
states this is deliberate until Stage 08 migrates the Library archetype —
`validate_project_spec` cannot succeed today for any input, by design.

`create-forge`'s bundled registry does not collect several fields ProjectSpec
requires (`package_name`, `repository_name`, `python.minimum`,
`python.development`) — `copier.yml` defaults them instead, per
`templates.toml`'s own header comment. Nothing in either repository names
which side derives them.

## Decision

**create-forge maps; forge-template validates.** A new pure module,
`src/create_forge/spec.py`, places CLI answers into their canonical
ProjectSpec position and omits values that are absent. It performs no
validation, re-derives no Python support window, and applies no default a
missing answer should instead surface as a structured, field-located error
from the engine. It imports nothing from `forge_template`, so it stays
importable and testable without the engine installed.

**The engine is touched in exactly one module.** `src/create_forge/engine.py`
is the only module permitted to import `forge_template` — the same rule
invariant 4 already states for `runner.py` and Copier's Python API, applied
to the new integration surface before it has a second caller to keep
consistent. `engine.py` negotiates the ProjectSpec protocol
(`get_engine_info`), parses (`parse_project_spec`), validates
(`validate_project_spec`), and translates `ForgeEngineError` into terminal
text. `tests/test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`
enforces the boundary: it parses every module reachable from
`create_forge.cli:app` and fails if any imports `forge_template` directly.

**`package_name` and `repository_name` are derived client-side.**
ProjectSpec makes both required wire fields, and the engine never derives
them from a project name — that is deliberately a client concern, since
different clients may want different derivation rules. `spec.py` derives
`package_name` by lower-casing and collapsing non-alphanumeric runs to a
single underscore, and `repository_name` by reusing `prompts.slugify()`,
the same function `runner.py`'s destination-slug logic already uses. Either
derivation is overridden by the matching Copier-style `--data` key
(`package_name`, `repo_name`), consistent with how `--data` already
suppresses a prompt today. The derivation deliberately does not reproduce
`copier.yml`'s own Jinja default expression byte-for-byte: ProjectSpec's
`package_name` pattern is stricter than Copier's, and the two systems are
allowed to diverge because the engine — not this derivation — is
authoritative for validity.

**Component identifiers are always caller-supplied.** `create-forge` mints
no archetype, capability, or platform identifier of its own. Today only test
code supplies them; CF-06.02 supplies them for real once `discover_components`
returns a non-empty catalogue. This keeps `create-forge` from inventing a
component vocabulary no manifest defines, which CF-06.01's own acceptance
criteria forbid.

**Validation runs the full ladder and characterizes today's failure.**
`engine.py` calls `validate_project_spec` rather than stopping at parsing,
so `tests/test_engine_adapter.py::test_validate_fails_closed_against_the_empty_catalogue`
documents the expected `invalid-component-selection` outcome against the
empty `0.2.0` catalogue. That test is written to start failing — not to stay
green — the moment Stage 08 lands a real manifest; replacing it with a
success assertion at that point is expected maintenance, not a regression.

**Exit status 3 is implemented at the boundary but not yet reachable.**
`engine.EngineCompatibilityError` carries the meaning
[ADR 0011](0011-engine-source-and-version-resolution.md) reserved for exit
status `3`, but no shipped command calls `negotiate_protocol` yet — `new`
is unchanged by this decision. `docs/cli-conventions.md`'s exit-status table
is updated to say so, rather than continuing to state that no code path can
produce it.

**The engine dependency is development-only, pinned, and unranged.** A new
`engine` dependency group depends on `forge-template` via a
`[tool.uv.sources]` git entry pinned to a commit SHA, not a tag or branch.
`[project.dependencies]` is unchanged, so no engine range is assigned and
`tests/test_engine_contract.py`'s existing ADR 0011/0012 guards, which read
`[project.dependencies]` only, continue to hold. A commit pin was chosen over
a tag: `forge-template`'s `v0.2.0` is not merely absent, tagging it is not a
side effect available to this decision — released `create-forge` v0.1.x
clients resolve `forge-template`'s *latest* PEP 440 tag for the Copier
template itself, so cutting `v0.2.0` would republish every `template/` change
made since `v0.1.1` to existing users in the same act. That is a coordinated
`forge-template` release decision, sequenced by
[the cross-repository contributor workflow](../cross-repository-workflow.md),
not a consequence of adding a development dependency here.

**`new` is unchanged.** This decision adds a construction boundary; it does
not wire it into any command. `create-forge new` keeps its v0.1.x Copier path
exactly as it is. CF-07.01 owns building "one canonical ProjectSpec-building
boundary used by interactive and non-interactive inputs" into the CLI itself.

## Consequences

- `spec.py` stays pure and engine-free, so its behaviour is characterized by
  `tests/test_spec.py` without the `engine` dependency group, while
  `tests/test_engine_adapter.py` exercises the real `forge_template` package
  the dev group already provides.
- A built wheel remains installable without `forge-template`: every job in
  CI already runs `uv sync --all-groups`, so the dev-only dependency is
  exercised continuously, but `test_shipped_cli_modules_do_not_import_the_engine`
  is what actually prevents a future change from silently making it load-
  bearing for `uvx create-forge` users.
- Today's registry answers (`github_org`, `build_backend`, `versioning`,
  `type_checking`, `use_docs`, `codeowners_team`) have no ProjectSpec home:
  no manifest declares them as options yet. `docs/project-spec-construction.md`
  records this as a known, expected gap CF-06.02 and Stage 08 close, rather
  than inventing option names ahead of the manifests that would own them.
- `test_validate_fails_closed_against_the_empty_catalogue` is a deliberately
  temporary characterization. Its failure mode flipping from
  `invalid-component-selection` to success is the signal that Stage 08's
  first manifest has landed and this adapter can be exercised for real.
- Assigning the first engine range remains blocked on more than a
  `forge-template` tag: [issue #9](https://github.com/Sandsy09/create-forge/issues/9)
  must also resolve, since a bounded range needs a distribution channel a
  pinned git commit cannot express.
- Nothing about v0.1.x behaviour changes. `create-forge new` scaffolds
  exactly as it did before this decision.
