# Rollout Regression and Failure Validation

This is the living evidence record for
[CF-14.03 / #113](https://github.com/Sandsy09/create-forge/issues/113): the
create-forge `0.3.0` candidate wheel retains every documented behaviour of the
paths [CF-14.02](installed-data-science-validation.md) did not touch — Library,
CLI Application, the default Copier path, and the no-engine command surface —
and fails at the documented exit status with nothing left behind. The decision
is accepted under
[ADR 0033](adr/0033-complete-rollout-regression-validation.md).

This record extends
[installed Data Science validation](installed-data-science-validation.md) from
the Data Science compositions to the rest of the CLI surface, at the same
release-candidate installation boundary. The editable-console suites
([end-to-end tests contract](end-to-end-tests.md)) keep proving the same paths
one layer in.

## Environments

`tests/test_e2e_installed_rollout.py` builds one `create_forge-0.3.0` wheel
(shared with CF-14.02 through `tests/conftest.py`'s `candidate_wheel` fixture)
and installs it three ways:

| Environment | Install | What it proves |
| --- | --- | --- |
| `installed_client` | `wheel[engine]` + `forge-template 0.4.1` | Library and CLI Application engine paths; the failure matrix; the atomic lock failure |
| `engineless_client` | `wheel` alone | the default Copier path from a wheel; `--version`, `list`, `doctor --json`, and `new --engine-preview`'s rejection with no engine installed |
| `out_of_range_client` | `wheel` + `forge-template 0.3.2` (real PyPI release below the supported range) | the exit-`3` compatibility boundary; `doctor` reporting the out-of-range package |

`forge-template 0.3.2` stays permanently below `compat.SUPPORTED_ENGINE_RANGE`
because [ADR 0012](adr/0012-engine-dependency-update-policy.md) only ever raises
that bound.

## What the executable evidence proves

| #113 criterion | Evidence |
| --- | --- |
| Every existing archetype and the default Copier workflow retains documented behavior | `test_installed_engine_archetype_*` (shape, current lock, owned-plan byte match, no Forge dependency, `cli` console name, `uv run --locked poe check`) parametrised over `library` and `cli`; `test_engineless_copier_generation_*` and `test_engineless_copier_project_passes_its_own_check` (clone, `_tasks`, `.copier-answers.yml` round-trip, `.git`/`uv.lock`, `uv run poe check`) |
| Compatibility failures retain their dedicated status and actionable diagnostics | `test_out_of_range_engine_is_rejected_before_any_write` (exit `3`, names `0.3.2` and the range, nothing written); `test_out_of_range_engine_is_visible_in_doctor` |
| Selection, validation, render, lock, and filesystem failures return the documented statuses | `test_installed_failure_case_is_rejected_cleanly` (15 parametrised cases across exit `1` and `2`); `test_installed_lock_failure_leaves_no_partial_project` (a real emptied-`PATH` lock failure, exit `1`); `test_installed_non_empty_destination_is_preserved` |
| All failure paths preserve destination contents and remove temporary state | every case above asserts the destination is absent or byte-identical to before and that no `.create-forge-*` staging sibling survives |
| Commands that do not use the engine remain usable without the engine extra | `test_engineless_version_is_the_candidate`, `test_engineless_list_shows_the_bundled_registry` (the wheel's `templates.toml` — CLAUDE.md invariant 5), `test_engineless_doctor_json_reports_the_absent_engine`, `test_engineless_engine_preview_is_rejected_with_guidance` |

| CF-EPIC-14 criterion | Evidence |
| --- | --- |
| Library and CLI Application engine-path E2E coverage remains green and the default Copier-path behavior is unchanged | the `test_installed_engine_archetype_*` and `test_engineless_copier_*` families above, plus the unchanged editable `tests/test_e2e_engine_generation.py` / `tests/test_e2e_generation.py` |
| Failure cases for missing/out-of-range engines, invalid selections, lock failure, and destination conflicts leave no partial project | `test_engineless_engine_preview_is_rejected_with_guidance` (missing engine), `test_out_of_range_engine_is_rejected_before_any_write`, the `test_installed_failure_case_is_rejected_cleanly` matrix, `test_installed_lock_failure_leaves_no_partial_project`, `test_installed_non_empty_destination_is_preserved` |

## The failure matrix

`test_installed_failure_case_is_rejected_cleanly` is parametrised over:

| Case | Status |
| --- | --- |
| unknown `--archetype`; `--archetype` without `--engine-preview`; `--engine-preview --yes` without `--archetype` | `1` |
| unknown `--capability`; wrong-kind `--capability library`; `--capability` + `--no-capabilities`; a selection flag without `--engine-preview` | `1` |
| `data-science` with the requirement absent, and again with `--no-capabilities` — each with the `Add --capability jupyter.` hint | `1` |
| `--component-option` for an unknown owner, for an unselected owner, and an undeclared option name (the engine's own verdict) | `1` |
| `--engine-preview` with `--template` | `1` |
| malformed `--data`; malformed `--component-option` | `2` |
| non-empty destination, engine path and Copier path | `1`, contents preserved |

## Recorded validation

The completed CF-14.03 implementation was validated on Windows on 2026-09-05:

| Command | Result |
| --- | --- |
| `uv run poe check` | formatting, lint, and typing passed; 363 tests passed, 75 deselected |
| `uv run pytest tests/test_e2e_installed_rollout.py tests/test_e2e_installed_data_science.py -m e2e` | 44 passed in 981.65s (cold uv cache) |
| `uv run poe test:e2e` | 67 passed, 371 deselected in 779.32s |
| `uv run poe check:adr` | `docs/adr/` internally consistent |
| `uv run poe check:wheel` | `create_forge/templates.toml` found in the fresh `0.3.0` wheel |

## Boundaries retained

This is an E2E test and documentation change only. No shipped module, public
API, CLI flag, schema, dependency range, protocol, component identifier,
runtime behaviour, or default path changes. `--engine-preview` remains hidden
and opt-in. CF-14.04 owns the create-forge `0.3.0` changelog, tag,
publication, and installed release verification, and the epic closure that
depends on it.

When this boundary or its evidence changes, update this record, the
[end-to-end tests contract](end-to-end-tests.md), and the executable suite in
the same pull request.
