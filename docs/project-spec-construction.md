# ProjectSpec Construction

This is the living contributor contract for how `create-forge` builds the
canonical [ProjectSpec](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
wire payload from CLI answers, and how it calls the `forge-template` engine
over it. [ADR 0010](adr/0010-public-engine-integration-contract.md) accepted
the public-engine target; [ADR 0013](adr/0013-projectspec-construction-boundary.md)
records the decision this document keeps current. Like
[`docs/engine-resolution.md`](engine-resolution.md) and
[`docs/engine-updates.md`](engine-updates.md), the *rules* below are the
contract — today's mechanisms will change as the engine cutover approaches.

## Status

The construction boundary exists and is fully tested, but nothing calls it
yet: `create-forge new` keeps its v0.1.x direct-Copier path unchanged.
CF-07.01 is the issue that wires this boundary into a command.
`forge-template`'s production component catalogue is intentionally empty
until Stage 08, so calling this boundary end-to-end always fails validation
today — see "Validation and today's expected failure" below.

## The map-vs-validate principle

`src/create_forge/spec.py` places present values in their canonical
ProjectSpec position and omits absent ones. It performs no validation, adds
no default beyond the two derivations named below, and never re-derives a
value `forge_template` itself computes (such as `python.tested_versions`). A
missing or malformed field becomes a structured, field-located
`ForgeEngineError` from `forge_template.parse_project_spec`, translated for
the terminal by `src/create_forge/engine.py`.

`engine.py` is the only module that imports `forge_template`, mirroring
[CLAUDE.md](../CLAUDE.md) invariant 4's rule that `runner.py` is the only
module touching Copier's Python API.
[`tests/test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`](../tests/test_engine_contract.py)
enforces this by parsing every module reachable from `create_forge.cli:app`.

## Field mapping

| CLI answer | ProjectSpec target | Note |
| --- | --- | --- |
| — | `protocol_version` | Constant `1`. |
| `project_name` | `project.name` | |
| *derived, or* `package_name` | `project.package_name` | Lower-cased, non-alphanumeric runs collapsed to one `_`. A `--data package_name=...` override wins. |
| *derived, or* `repo_name` | `project.repository_name` | Reuses `prompts.slugify()`. A `--data repo_name=...` override wins. |
| `project_description` | `project.description` | Passed through even when blank; omitted entirely (falls to the engine's own `""` default) when the answer is absent. |
| `license` | `project.licence` | Renamed — ProjectSpec uses the British spelling. |
| `author_name`, `author_email` | `project.authors` | Zero or one author. An email without a name is dropped: `Author` requires a name, so a lone email cannot form a valid entry. |
| `python_min_version` | `python.minimum` | Not currently prompted by `templates.toml`; see "Unmapped answers" below. |
| `python_version` | `python.development` | Same. `python` is omitted entirely unless *both* bounds are known — a partial `PythonSelection` is not a smaller valid one. |
| *caller-supplied* | `components.archetype`, `.capabilities`, `.platforms` | `create-forge` mints no component identifiers of its own (ADR 0013). Until CF-06.02 supplies them from `discover_components`, callers are responsible for values a real manifest will accept. |
| *caller-supplied* | `component_options` | Copied through unchanged, namespaced by component ID. |
| — | `provenance` | Left empty; Stage 09 (organisation-policy) work. |

## Unmapped answers

`templates.toml` collects several answers with no ProjectSpec home today,
because no component manifest declares them as options yet:
`github_org`, `build_backend`, `versioning`, `type_checking`, `use_docs`,
`codeowners_team`. This is an expected, temporary gap — CF-06.02's component
discovery adapter and Stage 08's Library manifest migration are what give
these a home, most likely under `component_options` namespaced by whichever
component ends up owning each one (a `github` platform, a `library`
archetype, and so on). This document does not invent those names ahead of
the manifests that will define them.

## Derivation rules

ProjectSpec requires `package_name` and `repository_name`; the engine never
derives them from a project name, since different clients may want different
rules. `create-forge` derives both from `project_name` when no explicit
override is present:

- `package_name`: lower-case, then collapse every run of characters outside
  `[a-z0-9]` to a single `_`, then trim leading/trailing `_`. Deliberately
  not `copier.yml`'s own Jinja default — ProjectSpec's `package_name` pattern
  (`^[a-z][a-z0-9_]*$`) is stricter than Copier's, and the engine, not this
  derivation, is authoritative for validity.
- `repository_name`: `prompts.slugify()` — the same function `runner.py`'s
  destination-slug logic already uses.

An explicit `--data package_name=...` or `--data repo_name=...` overrides the
corresponding derivation, consistent with how `--data` already suppresses a
registry prompt (see [`docs/cli-conventions.md`](cli-conventions.md)).

## Protocol negotiation and exit status 3

`engine.negotiate_protocol()` compares `create_forge.engine.SUPPORTED_PROJECTSPEC_PROTOCOLS`
— what this CLI release has implemented against — with the installed
engine's `get_engine_info().projectspec_protocols`. A disjoint set raises
`EngineCompatibilityError`, carrying the meaning
[ADR 0011](adr/0011-engine-source-and-version-resolution.md) reserved for
exit status `3`. Negotiation runs before parsing, so before any side effect.

This is implemented at the engine boundary but not yet reachable from any
shipped command: no code path calls `negotiate_protocol` until CF-07.01
wires the engine into `new`. `docs/cli-conventions.md`'s exit-status table
reflects this precisely — implemented, not yet raised by any command.

Negotiation checks the ProjectSpec wire protocol only, not the
`forge-template` package version: no engine range is assigned yet (see
[`docs/engine-resolution.md`](engine-resolution.md#assigning-the-first-engine-range)),
so there is no package-version range to check against.

## Validation and today's expected failure

`engine.validate()` calls `forge_template.validate_project_spec` against the
installed component catalogue. `forge-template` `0.2.0`'s production
catalogue is intentionally empty until Stage 08 migrates the Library
archetype, so validating any archetype selection fails today with
`EngineErrorCode.INVALID_COMPONENT_SELECTION` — by design, not by bug.
[`tests/test_engine_adapter.py::test_validate_fails_closed_against_the_empty_catalogue`](../tests/test_engine_adapter.py)
characterizes this outcome and is written to start failing, not stay green,
the moment a real manifest exists — replacing it with a success assertion at
that point is expected maintenance.

## Error presentation

`engine.explain()` formats a `ForgeEngineError`'s stable code and located
details into terminal-ready text, mirroring `runner._explain()`'s job for
Copier's freeform messages but working from a structured source instead of
pattern-matching message text.

## The engine dependency

`forge-template` is a development-only dependency today: a new `engine`
`uv` dependency group, resolved via a `[tool.uv.sources]` git entry pinned to
a commit SHA (not a tag or branch). `[project.dependencies]` is unchanged, so
no engine range is assigned and
[`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s
existing ADR 0011/0012 guards continue to hold.

A commit pin, not a tag: `forge-template` has no `v0.2.0` tag, and cutting
one is not a side effect available to this decision. Released `create-forge`
v0.1.x clients resolve `forge-template`'s *latest* PEP 440 tag for the Copier
template itself, so tagging `v0.2.0` would republish every `template/` change
made since `v0.1.1` to existing users in the same act — a coordinated
`forge-template` release decision, sequenced by
[the cross-repository contributor workflow](cross-repository-workflow.md),
not a consequence of this repository adding a development dependency.

## What changes next

- **CF-06.02** supplies real archetype/capability/platform identifiers from
  `discover_components()`, replacing today's caller-supplied placeholders.
- **CF-06.03** adds cross-repository contract tests exercising the exact
  supported package/protocol pair once one is assigned.
- **CF-07.01** wires this boundary into `create-forge new`, making
  `negotiate_protocol` and exit status `3` reachable for the first time.
- **Stage 08** (`forge-template`) migrates the Library archetype, giving the
  empty catalogue its first real manifest and flipping
  `test_validate_fails_closed_against_the_empty_catalogue` from a
  characterized failure to a real pass.

## Executable examples

- [`tests/test_spec.py`](../tests/test_spec.py) — derivation, `--data`
  overrides, field omission, and interactive/non-interactive parity, entirely
  without the `engine` dependency group.
- [`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py) —
  protocol negotiation (including the compatible real engine and a
  monkeypatched incompatible one), parsing, structured error translation, and
  the characterized empty-catalogue validation failure.
- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py) —
  `test_shipped_cli_modules_do_not_import_the_engine` guards the one-module
  import boundary.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
