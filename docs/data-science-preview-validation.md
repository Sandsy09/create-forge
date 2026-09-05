# Data Science Preview-Pipeline Validation

This is the living record of how CF-EPIC-13's acceptance checklist and its
final child, [CF-13.05 / #110](https://github.com/Sandsy09/create-forge/issues/110),
are proven — a map from each acceptance criterion to the named, CI-enforced
test that exercises it. It is the create-forge counterpart to forge-template's
[`docs/data-science-validation.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-validation.md),
which recorded the provider hand-off.

It is a sibling of the [component selection contract](component-selection.md),
the [component discovery contract](component-discovery.md), the
[ProjectSpec construction contract](project-spec-construction.md), the
[filesystem generation contract](filesystem-generation.md), and the
[end-to-end tests contract](end-to-end-tests.md) — this document adds no new
rule, it points at where the rules those contracts fix are checked for the
Data Science composition specifically.

## Status

Accepted as a contract under
[ADR 0030](adr/0030-data-science-preview-pipeline-validation.md). CF-13.05 is
implemented; CF-EPIC-13 is complete. CF-14.02 now extends this evidence through
the installed create-forge `0.3.0` candidate and reviewed engine under
[ADR 0032](adr/0032-validate-installed-data-science-generation.md). This is
**not** the CLI cutover: `--engine-preview` stays hidden and dev-only, and the
default `new` path is unchanged. CF-14.04
([ADR 0034](adr/0034-publish-0-3-0-and-close-roadmap-v2.md)) published
create-forge `0.3.0` and closed the roadmap.

## The composition under test

The full Data Science composition, discovered from the installed
`forge-template>=0.4.1,<0.5` engine:

| Component | Kind | Relationship |
| --- | --- | --- |
| `data-science` | archetype | requires `jupyter` |
| `jupyter` | capability | hard requirement of `data-science` |
| `scientific-python` | capability | independently optional |

The ids above appear in this document and in test fixtures feeding the real
engine. No shipped module names any of them — `tests/test_archetype_parity.py`'s
widened AST guard (ADR 0030, decision 6) enforces that.

## The client / engine validation split it exercises

`create-forge` checks only what is answerable from the discovered catalogue and
the resolved selection — an unknown or unselected `--component-option` owner, a
destination conflict, a package/protocol version outside
`compat.SUPPORTED_ENGINE_RANGE`. A missing hard requirement, an undeclared
option name, a wrong-typed value, a composition conflict — all stay engine
verdicts, surfaced through `engine.explain` before any destination effect.
`create-forge` adds no component to complete a selection; when `data-science`
is selected without `jupyter`, the request reaches the engine unchanged and
`cli._missing_requirement_hint` then names the flag that fixes it.

## CF-EPIC-13 acceptance criteria

| # | Criterion | Proven by |
| --- | --- | --- |
| 1 | #91 remains the engine-native option-prompting prerequisite | `tests/test_cli.py::test_new_engine_preview_interactive_asks_what_are_you_building_once`, and #91 itself (merged) |
| 2 | The CLI discovers archetypes and applicable capabilities through the facade, without copying a catalogue or hard-coding IDs | `tests/test_engine_adapter.py::test_discover_returns_the_real_production_catalogue`; `tests/test_archetype_parity.py::test_no_shipped_module_hardcodes_a_discovered_component_id` (widened) |
| 3 | Interactive and non-interactive inputs select Data Science and its capability combinations, including explicit-empty optional selections | `tests/test_data_science_pipeline.py::test_interactive_selection_pre_locks_the_required_capability`, `::test_selected_capabilities_round_trip_into_the_projectspec`, `::test_a_missing_required_capability_writes_nothing[--no-capabilities]` |
| 4 | Declared component options are prompted and serialised under their owning component namespaces | `tests/test_component_selection.py`'s `--component-option` section (CF-13.04); `tests/test_data_science_pipeline.py::test_an_undeclared_component_option_writes_nothing` (Data Science components declare none) |
| 5 | Compatibility, missing requirements, conflicts, invalid options, and engine failures produce actionable diagnostics before destination effects | `tests/test_data_science_pipeline.py`'s "failures leave no partial project" section — five cases, each asserting `not dst.exists()` |
| 6 | The shared pipeline, dry-run, staging, lock creation, and atomic finalisation work for Data Science with no archetype-specific branch | `tests/test_data_science_pipeline.py::test_a_full_composition_stages_locks_and_finalises`, `::test_dry_run_lists_every_planned_target_and_writes_nothing`; `tests/test_archetype_parity.py::test_every_archetype_renders_through_the_one_shared_pipeline`; `tests/test_pipeline.py::test_build_generation_request_succeeds_against_the_real_catalogue` |
| 7 | Library, CLI Application, the default Copier path, and no-engine-extra commands retain their documented behaviour | `tests/test_component_selection.py::test_every_discovered_archetype_generates_with_its_required_flags`; `tests/test_e2e_generation.py` (Copier path); `tests/test_e2e_engine_generation.py::test_a_missing_engine_extra_is_rejected_before_any_write` |

## CF-13.05 (#110) acceptance criteria

| # | Criterion | Proven by |
| --- | --- | --- |
| 1 | Valid Data Science requests produce locked projects through the same pipeline as existing archetypes | `tests/test_data_science_pipeline.py::test_a_full_composition_stages_locks_and_finalises`; `tests/test_e2e_engine_generation.py` parametrised over `_ARCHETYPES` (project shape, `uv lock --check`, `uv run --locked poe check`) |
| 2 | Invalid selections, options, compatibility, destination, and lock failures leave no partial project | `tests/test_data_science_pipeline.py::test_a_missing_required_capability_writes_nothing`, `::test_an_undeclared_component_option_writes_nothing`, `::test_an_incompatible_engine_writes_nothing`, `::test_a_non_empty_destination_is_rejected_before_the_engine`, `::test_a_lock_failure_leaves_no_partial_project` |
| 3 | Dry-run reports every planned target and writes nothing | `tests/test_data_science_pipeline.py::test_dry_run_lists_every_planned_target_and_writes_nothing` — the expected set is derived from a real render of the same selection |
| 4 | No create-forge branch selects behaviour by a hard-coded Data Science component ID | `tests/test_archetype_parity.py::test_no_shipped_module_hardcodes_a_discovered_component_id` (widened to every string literal); the three discovery-driven parametrisations in `test_archetype_parity.py`, `test_pipeline.py`, `test_component_selection.py` |
| 5 | The Stage 13 epic acceptance checklist has executable evidence | this document |

## CF-14.02 (#112) installed-candidate evidence

The canonical
[installed Data Science validation](installed-data-science-validation.md)
record maps all four #112 acceptance criteria to
`tests/test_e2e_installed_data_science.py`. That suite builds and installs the
create-forge `0.3.0` wheel with published `forge-template 0.4.1`, generates
both accepted compositions twice through its console script, compares
rendered output and client-owned locks byte-for-byte, and validates locked
restoration, notebook execution, Scientific Python smoke behavior, wheel/sdist
contents, and Forge-free isolated installation. The full composition also
runs at Python 3.11 and 3.14.

## Where the coverage lives

- **Fast suite** (`uv run poe check`): `tests/test_data_science_pipeline.py`
  and the generalised parametrisations. Real installed engine, no network.
- **`e2e`** (`uv run poe test:e2e`): `tests/test_e2e_engine_generation.py`
  generates `data-science --capability jupyter --capability scientific-python`
  through the real console script and runs the generated project's own
  `uv run --locked poe check`; `tests/test_e2e_installed_data_science.py`
  separately validates the built candidate wheel and both accepted
  compositions. CI's `e2e` job budget is `timeout-minutes: 45`.

When a Data Science acceptance rule or its evidence changes, update this
document and the test it names in the same pull request.
