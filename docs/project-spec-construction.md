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
[filesystem generation contract](filesystem-generation.md). CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) moved the
development pin to `forge-template==0.3.0`, whose production catalogue ships
both `library` and `cli` — calling this boundary end-to-end now succeeds,
generating a real project, rather than failing validation as it did against
the prior empty catalogue; see "Validation" below.

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
| `python_min_version` | `python.minimum` | Not currently prompted by `templates.toml`; see "Unmapped answers" below. Falls back to `spec.DEFAULT_PYTHON_MINIMUM` (`"3.11"`, mirroring `copier.yml`'s own default) when absent (CF-08.02). |
| `python_version` | `python.development` | Same, falling back to `spec.DEFAULT_PYTHON_DEVELOPMENT` (`"3.13"`). Each bound resolves independently — `python` is a required ProjectSpec field, so it is always present in the payload, never omitted. |
| *discovered, then user- or caller-selected* | `components.archetype`, `.capabilities`, `.platforms` | `create-forge` mints no component identifiers of its own (ADR 0013). The [component discovery adapter](component-discovery.md) supplies engine-owned descriptors; `--engine-preview` now drives selection from discovery for real, via a hidden `--archetype` option or an interactive prompt over `pipeline.discover_archetypes()` (CF-08.02, [ADR 0017](adr/0017-cli-application-archetype-exposure.md)). `capabilities`/`platforms` remain unselected — no discovered descriptor of either kind exists yet. |
| *caller-supplied, or derived for `library`* | `component_options` | Copied through unchanged, namespaced by component ID, when the caller supplies it. When it does not and the archetype is `library`, `pipeline._resolved_component_options` derives `packaging_mode` from the legacy `build_backend`/`versioning` answers via `spec.legacy_library_answers` and `engine.map_legacy_library_options` (CF-08.02) — see "Unmapped answers" below. |
| — | `provenance` | Left empty; Stage 09 (organisation-policy) work. |

## Unmapped answers

`templates.toml` collects several answers with no ProjectSpec home:
`github_org`, `type_checking`, `use_docs`, `codeowners_team` remain
genuinely unmapped today — no component manifest declares them as options
yet. `build_backend`/`versioning` are the exception, and CF-08.02 closes
that gap on the engine path. The canonical
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
fixes the packaging mapping, and `forge-template`'s public
`map_legacy_library_answers()` facade implements it:

- `build_backend=uv_build` becomes
  `component_options.library.packaging_mode=uv-build-static`;
- `build_backend=hatchling` with absent or static versioning becomes
  `hatchling-static`; and
- `build_backend=hatchling` with VCS versioning becomes `hatchling-vcs`.

`spec.legacy_library_answers()` resolves the same `versioning_resolved`
value `copier.yml` itself computes (`static` when `build_backend ==
"uv_build"`, else `versioning`, defaulting to `static`), and
`engine.map_legacy_library_options()` is a thin, compatibility-checked
wrapper over the facade. `pipeline._resolved_component_options` calls both,
but only when the caller supplied no explicit `component_options` and the
archetype is `library` — this is the one archetype-specific branch in this
codebase, kept narrow by keying it on the engine's own
`map_legacy_library_answers` naming rather than a locally maintained
archetype list. The remaining unmapped answers retain the owner assigned by
their eventual component, such as a GitHub platform or optional capability,
and stay unmapped until that component exists.

The accepted
[CLI Application archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
assigns the engine-owned ID `cli`, declares no component options, and derives
its console command from `project.repository_name`. `create-forge` must not add
a duplicate `command_name` field or recreate CLI component metadata in its own
models or registry — `--archetype cli` therefore never derives
`component_options` for it.

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
package version `0.3.0`. This is the development contract CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) moved to, not a
released package range; see the
[cross-repository engine contract tests](engine-contract-tests.md).

This is reachable from a real command as of CF-07.01, but only behind
`new --engine-preview` — see [ADR 0014](adr/0014-lazy-engine-reachability.md).
`docs/cli-conventions.md`'s exit-status table reflects this precisely.

No bounded runtime engine range is checked yet. The exact development version
guard is replaced by the installable lower/upper range only at the atomic
cutover described by
[`docs/engine-resolution.md`](engine-resolution.md#assigning-the-first-engine-range).

## Validation

`engine.validate()` calls `forge_template.validate_project_spec` against the
installed component catalogue. `forge-template` `0.3.0`'s production
catalogue ships both `library` and `cli` at the exact pinned tag, so
validating either archetype selection now succeeds.
[`tests/test_engine_adapter.py::test_validate_succeeds_against_the_real_production_catalogue`](../tests/test_engine_adapter.py)
characterizes this outcome for the pinned pair, replacing the Stage 06-era
empty-catalogue characterization its own docstring anticipated retiring.

## Error presentation

`engine.explain()` formats a `ForgeEngineError`'s stable code and located
details into terminal-ready text, mirroring `runner._explain()`'s job for
Copier's freeform messages but working from a structured source instead of
pattern-matching message text.

## The engine dependency

`forge-template` is a development-only dependency today: an `engine` `uv`
dependency group constrained to `forge-template==0.3.0`, resolved via a
`[tool.uv.sources]` git entry pinned to `tag = "v0.3.0"` — moved from a
commit SHA to a tag by CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)), which also
adopted the `library`/`cli` production catalogue; CF-07.04
([ADR 0015](adr/0015-staged-filesystem-generation.md)) had moved the prior
commit pin once already, within the earlier unreleased `0.2.0` contract, to
adopt generated-project validation.
`[project.dependencies]` is unchanged, so
no engine range is assigned and
[`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s
existing ADR 0011/0012 guards continue to hold.

A tag, not a commit pin, unlike the prior `0.2.0` contract: `forge-template`
had no `v0.2.0` tag, and cutting one was not a side effect available to that
decision, since released `create-forge` v0.1.x clients resolve
`forge-template`'s *latest* PEP 440 tag for the Copier template itself — see
[ADR 0013](adr/0013-projectspec-construction-boundary.md) for that reasoning
in full. `v0.3.0` is a real, independent release that reasoning does not
apply to, so ADR 0017 names it directly.

## What changes next

- **CF-06.03** proves the exact development package/protocol pair, including
  fail-closed public-facade rendering against the (then-empty) production
  catalogue.
- **CF-07.01** wires this boundary into `create-forge new --engine-preview`
  (ADR 0014), making ProjectSpec construction,
  [component discovery](component-discovery.md), and exit status `3`
  reachable for the first time — behind a hidden, opt-in flag, not the
  default `new` path.
- **CF-07.04** ([ADR 0015](adr/0015-staged-filesystem-generation.md)) consumes
  the `GenerationRequest` `src/create_forge/pipeline.py` produces, staging and
  finalising it exactly like the Copier path — see the canonical
  [filesystem generation contract](filesystem-generation.md).
- **FT-08.02** migrated the Library archetype into `forge-template/main`,
  released at `0.3.0`. **FT-08.03**/**FT-08.04** selected and implemented the
  optionless `cli` archetype in the same release; its
  [canonical contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
  fixes identity and `repository_name` command derivation.
- **CF-08.02** ([ADR 0017](adr/0017-cli-application-archetype-exposure.md))
  moves this repository's exact pin to `0.3.0`, adds discovery-driven
  archetype selection to `--engine-preview`, and derives the legacy
  `library` option mapping described above. `--engine-preview` now succeeds
  end-to-end for both archetypes. The atomic cutover that replaces
  `--engine-preview` and the exact development-package assertion with a
  bounded runtime dependency still waits on
  [#9](https://github.com/Sandsy09/create-forge/issues/9) resolving a
  distribution channel.

## Executable examples

- [`tests/test_spec.py`](../tests/test_spec.py) — derivation, `--data`
  overrides, field omission, Python-bound fallback, legacy Library answer
  resolution, and interactive/non-interactive parity, entirely without the
  `engine` dependency group.
- [`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py) —
  protocol negotiation (including the compatible real engine and a
  monkeypatched incompatible one), parsing, structured error translation, the
  real production-catalogue validation and render, and the legacy Library
  option mapping.
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
  real, unmocked end-to-end success against the production catalogue for
  both archetypes, the legacy `library` option derivation and its
  archetype-scoping, `discover_archetypes()`'s `kind` filter, and
  `finalise_generation_request`'s staging/rename behaviour — see also the
  canonical [filesystem generation contract](filesystem-generation.md).
- [`tests/test_cli.py`](../tests/test_cli.py) — `--engine-preview`'s outcomes
  (dependency missing, a real generated project, exit `3` on an incompatible
  engine, a pre-existing destination conflict), `--archetype`'s explicit,
  `--yes`-without-one, unknown-id, and interactive-prompt paths, and that
  omitting `--engine-preview` leaves `new` unchanged.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
