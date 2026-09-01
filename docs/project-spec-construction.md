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
`forge-template` is the optional `engine` extra (ADR 0018), not installed by
a plain `pip install create-forge`, so `cli.py` cannot import the engine
unconditionally without breaking every real `uvx create-forge` install. That
reasoning is unaffected by the extra now having a real released range rather
than a development-only pin: it is still optional, still absent by default.
CF-07.04 ([ADR 0015](adr/0015-staged-filesystem-generation.md))
completed the flag: it now stages a successful render adjacent to the
computed destination and finalises it by atomic rename, exactly like the
Copier path, through `src/create_forge/pipeline.py`'s
`finalise_generation_request` — see the canonical
[filesystem generation contract](filesystem-generation.md). CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) moved the
development pin to `forge-template==0.3.0`, whose production catalogue ships
both `library` and `cli` — calling this boundary end-to-end now succeeds,
generating a real project, rather than failing validation as it did against
the prior empty catalogue; see "Validation" below. #9
([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)) then
replaced that development pin with a released range,
`forge-template>=0.3.1,<0.4`, changing nothing about this boundary's
reachability or behaviour.

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

## Policy-resolution boundary

The canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
is resolved by a downstream client before it constructs the effective
ProjectSpec. Policy documents are not embedded in ProjectSpec: after successful
resolution, only the effective component selections and the applied policy IDs
in `SelectionProvenance.policies` cross the engine boundary.

A policy-aware client must retain whether the archetype, capability list, and
platform list were explicitly supplied. In particular, an explicit empty list
replaces defaults for that selection kind, while an absent input permits
defaults. CF-09.01 ([ADR 0022](adr/0022-downstream-organisation-policy-hook.md))
delivered the consumption hook: `spec.SelectionRequest`/`SelectionProvenance`
carry that distinction, and `pipeline.build_generation_request` accepts them
as `selection`/`provenance` keywords immediately upstream of ProjectSpec
construction. `create-forge` itself still collects or resolves no
organisation policy and reads no policy document — that is a deliberate
boundary, not a gap, recorded in full by the canonical
[downstream policy-consumption contract](organisation-policy-consumption.md).

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
| *discovered, then user- or caller-selected, via* `SelectionRequest` | `components.archetype`, `.capabilities`, `.platforms` | `create-forge` mints no component identifiers of its own (ADR 0013). The [component discovery adapter](component-discovery.md) supplies engine-owned descriptors; `--engine-preview` now drives selection from discovery for real, via a hidden `--archetype` option or an interactive prompt over `pipeline.discover_archetypes()` (CF-08.02, [ADR 0017](adr/0017-cli-application-archetype-exposure.md)). `capabilities`/`platforms` remain unselected — no discovered descriptor of either kind exists yet. `spec.SelectionRequest` (CF-09.01, [ADR 0022](adr/0022-downstream-organisation-policy-hook.md)) additionally carries whether each kind was an explicit choice, for a policy-aware caller; that fact never reaches the wire payload itself. |
| *caller-supplied, or derived when the selected archetype declares it* | `component_options` | Since #91 ([ADR 0025](adr/0025-engine-native-prompt-flow.md)), `--engine-preview` prompts directly for the selected archetype's own declared `ComponentDescriptor.options` (`prompts.ask_component_options`) and passes an explicit, caller-supplied `component_options` whenever any were answered. When none were — the archetype declares none, or every value came from elsewhere — `pipeline._resolved_component_options` falls back to deriving `packaging_mode` from the legacy `build_backend`/`versioning` `--data` answers via `spec.legacy_library_answers` and `engine.map_legacy_library_options` (CF-08.02), applied only when the selected archetype's own descriptor declares that name (CF-08.03, [ADR 0019](adr/0019-cli-archetype-parity-review.md)) — see "Unmapped answers" below. |
| *caller-supplied* `SelectionProvenance` | `provenance` | Left empty by `cli.py` today, since it resolves no policy. A policy-aware client passes a `SelectionProvenance` built after resolving the canonical organisation-policy protocol; ProjectSpec never carries the policy document itself — see the canonical [downstream policy-consumption contract](organisation-policy-consumption.md). |

## Unmapped answers

`templates.toml` collects several answers with no ProjectSpec home:
`github_org`, `type_checking`, `use_docs`, `codeowners_team` remain
genuinely unmapped today — no component manifest declares them as options
yet, and since #91 ([ADR 0025](adr/0025-engine-native-prompt-flow.md)) the
engine path does not even read them from a registry; a `--data` value for one
of them is simply preset data with no declared option name to match, and
flows through unused. `build_backend`/`versioning` are the one pair with a
real mapping, and CF-08.02 closes that gap on the engine path — reachable
today only as a `--data`-only fallback (see "Field mapping" above), since the
engine path prompts `library`'s `packaging_mode`/`initial_version` options
directly. The canonical
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
but only when the caller supplied no explicit `component_options` *and* the
selected archetype's own discovered `ComponentDescriptor.options` declares
`packaging_mode` — `library`'s manifest does, so it applies there; `cli`
declares no options at all, so the derivation is skipped before
`map_legacy_library_options` is even called. CF-08.03's archetype-parity
review ([ADR 0019](adr/0019-cli-archetype-parity-review.md)) generalised this
from an earlier `archetype != "library"` check to this descriptor-gated form,
so no archetype id is hardcoded here or anywhere else in `src/create_forge/`
— a future archetype that also declares `packaging_mode` (or `library` being
renamed) needs no change to this function, only to the engine's own
manifest. The remaining unmapped answers retain the owner assigned by their
eventual component, such as a GitHub platform or optional capability, and
stay unmapped until that component exists.

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

`engine.negotiate_protocol()` compares `compat.SUPPORTED_PROJECTSPEC_PROTOCOLS`
— what this CLI release has implemented against — with the installed
engine's `get_engine_info().projectspec_protocols`. A disjoint set raises
`EngineCompatibilityError`, carrying the meaning
[ADR 0011](adr/0011-engine-source-and-version-resolution.md) reserved for
exit status `3`. Negotiation runs before parsing, so before any side effect.
`SUPPORTED_PROJECTSPEC_PROTOCOLS` lives in `src/create_forge/compat.py`, not
`engine.py` — it moved there with ADR 0018 so `cli.py`'s `doctor` can report
it without importing the engine; `engine.py` imports it from `compat.py` like
everything else there.

Before that protocol comparison, `engine._require_supported_package` checks
the installed package version against `compat.SUPPORTED_ENGINE_RANGE`
(`forge-template>=0.3.1,<0.4`) with `packaging.specifiers.SpecifierSet` — a
real, released, bounded range as of #9
([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)), not
the exact-equality development pin `0.3.0` that preceded it; see the
[cross-repository engine contract tests](engine-contract-tests.md).

This is reachable from a real command as of CF-07.01, but only behind
`new --engine-preview` — see [ADR 0014](adr/0014-lazy-engine-reachability.md).
`docs/cli-conventions.md`'s exit-status table reflects this precisely.

## Validation

`engine.validate()` calls `forge_template.validate_project_spec` against the
installed component catalogue. `forge-template`'s production catalogue
(released at `0.3.0` and unchanged in substance through the `0.3.1`
packaging patch #9 assigns as the installable lower bound) ships both
`library` and `cli`, so validating either archetype selection succeeds.
[`tests/test_engine_adapter.py::test_validate_succeeds_against_the_real_production_catalogue`](../tests/test_engine_adapter.py)
characterizes this outcome against the real installed engine, replacing the
Stage 06-era empty-catalogue characterization its own docstring anticipated
retiring.

## Error presentation

`engine.explain()` formats a `ForgeEngineError`'s stable code and located
details into terminal-ready text, mirroring `runner._explain()`'s job for
Copier's freeform messages but working from a structured source instead of
pattern-matching message text.

## The engine dependency

`forge-template` is the optional `engine` extra as of #9
([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)):
`[project.optional-dependencies].engine = ["forge-template>=0.3.1,<0.4"]`,
resolved from PyPI like any other dependency -- no `[tool.uv.sources]`
override, no dev-only dependency group. `[project.dependencies]` remains
unaffected, so `create-forge` itself (`pip install create-forge`, or `uvx
create-forge`) never resolves it; only `pip install 'create-forge[engine]'`
or `uv sync --all-extras` does.
[`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s ADR
0011/0012 guards continue to hold: the range has a tested lower bound and a
strict upper bound, and Dependabot is gated from crossing it unattended.

Before this, the dependency was development-only: `forge-template==0.3.0`
via an `engine` `uv` dependency group and a `[tool.uv.sources]` git entry
pinned to `tag = "v0.3.0"` -- moved from a commit SHA to a tag by CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)), and from a
commit within the earlier unreleased `0.2.0` contract by CF-07.04
([ADR 0015](adr/0015-staged-filesystem-generation.md)) before that, to adopt
generated-project validation. `0.3.1` -- the version now declared -- is a
packaging-only patch over that same `0.3.0` production catalogue, published
by
[forge-template ADR 0036](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0036-publish-the-engine-to-pypi.md).

## What changes next

- **CF-06.03** proved the exact development package/protocol pair, including
  fail-closed public-facade rendering against the (then-empty) production
  catalogue.
- **CF-07.01** wired this boundary into `create-forge new --engine-preview`
  (ADR 0014), making ProjectSpec construction,
  [component discovery](component-discovery.md), and exit status `3`
  reachable for the first time — behind a hidden, opt-in flag, not the
  default `new` path.
- **CF-07.04** ([ADR 0015](adr/0015-staged-filesystem-generation.md)) consumed
  the `GenerationRequest` `src/create_forge/pipeline.py` produces, staging and
  finalising it exactly like the Copier path — see the canonical
  [filesystem generation contract](filesystem-generation.md).
- **FT-08.02** migrated the Library archetype into `forge-template/main`,
  released at `0.3.0`. **FT-08.03**/**FT-08.04** selected and implemented the
  optionless `cli` archetype in the same release; its
  [canonical contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
  fixes identity and `repository_name` command derivation.
- **CF-08.02** ([ADR 0017](adr/0017-cli-application-archetype-exposure.md))
  moved this repository's exact pin to `0.3.0` and added discovery-driven
  archetype selection to `--engine-preview` and the legacy `library` option
  mapping described above. `--engine-preview` succeeds end-to-end for both
  archetypes.
- **#9** ([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md))
  replaced the exact development pin above with the first released,
  installable range. The atomic cutover that replaces `--engine-preview` and
  `--template-url` with the engine as the default path remains a future,
  unfiled decision -- it is no longer blocked on a distribution channel, only
  on that decision being made.
- **CF-08.03** ([ADR 0019](adr/0019-cli-archetype-parity-review.md)) reviewed
  both archetypes for parity, confirmed the shared ProjectSpec/pipeline path
  and engine-owned discovery hold, and generalised the legacy `library`
  option derivation above to be gated by the selected archetype's own
  discovered descriptor rather than a hardcoded id. It also recorded, without
  fixing, that the engine path's prompt set is still the Copier registry's
  Library-shaped questions -- tracked by
  [#91](https://github.com/Sandsy09/create-forge/issues/91) rather than made
  here, since fixing it changes documented `--engine-preview` contract
  behaviour (see [`docs/cli-conventions.md`](cli-conventions.md)).
- **CF-09.01** ([ADR 0022](adr/0022-downstream-organisation-policy-hook.md))
  delivered the downstream policy-consumption hook: `spec.SelectionRequest`/
  `SelectionProvenance` and `pipeline.build_generation_request`'s
  `selection`/`provenance` keywords. `create-forge` itself resolves no
  policy — see the canonical
  [downstream policy-consumption contract](organisation-policy-consumption.md).
- **#91** ([ADR 0025](adr/0025-engine-native-prompt-flow.md)) closed the gap
  CF-08.03 recorded without fixing: `--engine-preview` now prompts directly
  from the selected archetype's own discovered `ComponentDescriptor.options`
  instead of the Copier registry's Library-shaped questions, and reads no
  registry data at all on this path.

## Executable examples

- [`tests/test_spec.py`](../tests/test_spec.py) — derivation, `--data`
  overrides, field omission, Python-bound fallback, legacy Library answer
  resolution, and interactive/non-interactive parity, entirely without the
  optional `engine` extra installed.
- [`tests/test_policy_hook.py`](../tests/test_policy_hook.py) — the
  `SelectionRequest`/`SelectionProvenance` seam: the absent-vs-explicit-empty
  distinction, provenance omission and emission, and the containment guard
  on both types' field sets and shapes.
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
  both archetypes, the legacy `library` option derivation gated by
  discovered descriptor (CF-08.03), `discover_archetypes()`'s `kind` filter,
  and `finalise_generation_request`'s staging/rename behaviour — see also the
  canonical [filesystem generation contract](filesystem-generation.md).
- [`tests/test_archetype_parity.py`](../tests/test_archetype_parity.py) — the
  CF-08.03 review's executable record: shared payload shape, shared pipeline,
  `cli`'s empty-options descriptor driving empty `component_options`, no
  `command_name` anywhere, `repository_name` as the sole command identity,
  and an AST guard against any shipped module hardcoding a component id
  again.
- [`tests/test_cli.py`](../tests/test_cli.py) — `--engine-preview`'s outcomes
  (dependency missing, a real generated project, exit `3` on an incompatible
  engine, a pre-existing destination conflict), `--archetype`'s explicit,
  `--yes`-without-one, unknown-id, and interactive-prompt paths, and that
  omitting `--engine-preview` leaves `new` unchanged. Its engine-native-
  prompting block (#91, [ADR 0025](adr/0025-engine-native-prompt-flow.md))
  covers `cli` asking no Library question, `library` asking exactly its
  declared options with the answered `packaging_mode` reaching
  `component_options`, the registry never being loaded, the single "What are
  you building?" prompt, `--template`/`--template-url`/`--ref` being
  rejected with `--engine-preview`, and the legacy `--data`
  `build_backend`/`versioning` fallback.
- [`tests/test_prompts.py`](../tests/test_prompts.py) — `ask_project_answers`
  and `ask_component_options` (ADR 0025): preset/defaults/cancellation
  parity with `ask_all`, one case per declared option `type`, and the
  empty-return case for a descriptor with no options.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
