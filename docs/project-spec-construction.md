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

The construction boundary is reachable from a real command, but only behind
a hidden, opt-in flag: `create-forge new --engine-preview`. Without that
flag, `new` keeps its v0.1.x direct-Copier path completely unchanged. [ADR
0014](adr/0014-lazy-engine-reachability.md) records why a hidden flag with a
lazy import, rather than a default-path cutover, is what CF-07.01 shipped —
`forge-template` remains a development-only dependency, so `cli.py` cannot
import the engine unconditionally without breaking every real `uvx
create-forge` install. CF-07.04 ([ADR 0015](adr/0015-staged-filesystem-generation.md))
completed the flag: it now stages a successful render adjacent to the
computed destination and finalises it by atomic rename, exactly like the
Copier path, through `src/create_forge/pipeline.py`'s
`finalise_generation_request` — see the canonical
[filesystem generation contract](filesystem-generation.md). `forge-template`'s
production component catalogue is intentionally empty until Stage 08, so
calling this boundary end-to-end always fails validation today, before any
staging happens — see "Validation and today's expected failure" below.

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
| *discovered, but caller-selected* | `components.archetype`, `.capabilities`, `.platforms` | `create-forge` mints no component identifiers of its own (ADR 0013). The [component discovery adapter](component-discovery.md) supplies engine-owned descriptors; `--engine-preview` today passes `archetype=template.id` with empty capabilities/platforms rather than driving real selection from discovery — nothing non-empty to select until Stage 08 (ADR 0014). |
| *caller-supplied* | `component_options` | Copied through unchanged, namespaced by component ID. |
| — | `provenance` | Left empty; Stage 09 (organisation-policy) work. |

## Unmapped answers

`templates.toml` collects several answers with no ProjectSpec home today,
because no component manifest declares them as options yet:
`github_org`, `build_backend`, `versioning`, `type_checking`, `use_docs`,
`codeowners_team`. This is an expected, temporary gap: the discovery adapter
preserves option declarations, but the empty production catalogue declares
none yet. Stage 08's Library manifest migration is what gives these answers a
home under `component_options` namespaced by their owning component. The
canonical
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
now fixes the packaging mapping that FT-08.02 must implement:

- `build_backend=uv_build` becomes
  `component_options.library.packaging_mode=uv-build-static`;
- `build_backend=hatchling` with absent or static versioning becomes
  `hatchling-static`; and
- `build_backend=hatchling` with VCS versioning becomes `hatchling-vcs`.

The remaining answers retain the owner assigned by their eventual component,
such as a GitHub platform or optional capability. Current CLI code still maps
none of these values into component options because the production catalogue
is empty; this link-only record does not pre-empt FT-08.02 or the CLI cutover.

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

Before that protocol comparison, the development adapter requires exact
package version `0.2.0`. This is the Stage 06 development contract, not a
released package range; see the
[cross-repository engine contract tests](engine-contract-tests.md).

This is reachable from a real command as of CF-07.01, but only behind
`new --engine-preview` — see [ADR 0014](adr/0014-lazy-engine-reachability.md).
`docs/cli-conventions.md`'s exit-status table reflects this precisely.

No bounded runtime engine range is checked yet. The exact development version
guard is replaced by the installable lower/upper range only at the atomic
cutover described by
[`docs/engine-resolution.md`](engine-resolution.md#assigning-the-first-engine-range).

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

`forge-template` is a development-only dependency today: an `engine` `uv`
dependency group constrained to `forge-template==0.2.0`, resolved via a
`[tool.uv.sources]` git entry pinned to the full commit SHA
`bb5f6a7106b09176c8c5991f43d22ccdf8a05d3c` (not a tag or branch) — moved
forward once from Stage 06's original pin by CF-07.04
([ADR 0015](adr/0015-staged-filesystem-generation.md)) to adopt generated-
project validation, within the same `0.2.0` development contract.
`[project.dependencies]` is unchanged, so
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

- **CF-06.03** proves the exact development package/protocol pair, including
  fail-closed public-facade rendering against the empty production catalogue.
- **CF-07.01** wires this boundary into `create-forge new --engine-preview`
  (ADR 0014), making ProjectSpec construction,
  [component discovery](component-discovery.md), and exit status `3`
  reachable for the first time — behind a hidden, opt-in flag, not the
  default `new` path.
- **CF-07.04** ([ADR 0015](adr/0015-staged-filesystem-generation.md)) consumes
  the `GenerationRequest` `src/create_forge/pipeline.py` produces, staging and
  finalising it exactly like the Copier path — see the canonical
  [filesystem generation contract](filesystem-generation.md). The atomic
  cutover that replaces `--engine-preview` and the exact development-package
  assertion with a bounded runtime dependency still waits on
  [#9](https://github.com/Sandsy09/create-forge/issues/9) resolving a
  distribution channel.
- **Stage 08** (`forge-template`) migrates the Library archetype, giving the
  empty catalogue its first real manifest and flipping
  `test_validate_fails_closed_against_the_empty_catalogue` from a
  characterized failure to a real pass. The accepted
  [Library contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
  defines that migration without changing this repository's current adapter.

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
- [`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py)
  — exact package/protocol agreement and fail-before-engine-call behavior,
  runnable against either the immutable pin or a sibling working tree, and
  the adopted `validate_rendered_project` contract against the real pinned
  engine.
- [`tests/test_pipeline.py`](../tests/test_pipeline.py) — the shared
  pipeline's discover → build → validate → render orchestration order, the
  real, unmocked end-to-end characterized failure against the empty
  catalogue, and `finalise_generation_request`'s staging/rename behaviour —
  see also the canonical [filesystem generation contract](filesystem-generation.md).
- [`tests/test_cli.py`](../tests/test_cli.py) — `--engine-preview`'s outcomes
  (dependency missing, characterized validation failure, exit `3` on an
  incompatible engine, a pre-existing destination conflict), and that
  omitting it leaves `new` unchanged.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
