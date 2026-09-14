# Engine-Default Cutover Installed Validation

This is the living evidence record for
[CF-18.06 / #163](https://github.com/Sandsy09/create-forge/issues/163):
completing the installed-console acceptance evidence
[docs/engine-cutover-acceptance.md](engine-cutover-acceptance.md)'s matrix
assigns it, and bringing `docs/user-guide/` back in step with the shipped
cutover. The decision is accepted under
[ADR 0048](adr/0048-installed-cutover-acceptance-evidence.md).

This record extends
[rollout regression and failure validation](rollout-regression-validation.md)
(CF-14.03) — it maps every CF-18.06-owned matrix row, including rows where
the rollout suite's pre-existing coverage already discharges most of the
row, so nothing is silently uncounted.

## Environments

`tests/test_e2e_installed_cutover.py` (CF-18.05, extended by CF-18.06)
reuses `tests/conftest.py`'s session `candidate_wheel` and
`tests/installed_client.py`'s `build_client`, plus two install shapes
`build_client` cannot express — `uvx --from <wheel>` and
`uv tool install <wheel>` — built with small local helpers in the suite
itself (ADR 0048 decision 6: kept local rather than added to the shared
harness, since only this file needs them).

| Environment | Install | What it proves |
| --- | --- | --- |
| `uvx --from <wheel>` | ephemeral, uv-managed | row 172's "Ephemeral" mode |
| `uv tool install <wheel>` | persistent, uv-managed | row 172's "Persistent" mode |
| `build_client(candidate_wheel, e2e_child_env)` | `pip install`-equivalent, no extra | row 172's "Environment" mode |
| `installed_client` (session, `[legacy]` + pinned `forge-template==0.5.0`) | `create-forge[legacy]` | row 172's "Legacy route" mode; CF-18.05's own legacy/preview rows |
| `build_client(..., force_version="0.3.2")` | a real, permanently out-of-range engine | rows 219-220's cutover-specific incompatible/boundary cases |
| `build_client(..., omit="forge-template")` | no engine at all | row 220's cutover-specific no-engine boundary case |

## What the executable evidence proves

| Row | Check | Evidence |
| --- | --- | --- |
| 172 | Each of the four install modes resolves the engine and generates from an isolated environment | `test_install_modes_uvx_ephemeral_resolves_and_generates`, `test_install_modes_uv_tool_install_resolves_and_generates`, `test_install_modes_pip_install_resolves_and_generates`, `test_install_modes_legacy_extra_resolves_and_generates`, `test_install_modes_python_window_edge` (Python window edges 3.11/3.14; the rest of the window is the `test` CI matrix and `floor` job) |
| 219 (cutover-specific slice) | An incompatible engine, an invalid selection, and a failure each fail with a stable, correct-class status | `test_incompatible_engine_native_update_fails_closed_at_exit_3` (exit `3`, not the engine-source worker's own former internal-error bug this issue also fixed — see below); `test_invalid_degraded_with_an_unusable_engine_exits_1`; `test_failure_engine_native_degraded_update_refuses_to_overwrite_a_diverged_edit` |
| 219 (pre-existing, mapped not repeated) | The rest of the selection/option/destination/lock/cleanup failure matrix | `tests/test_e2e_installed_rollout.py::test_installed_failure_case_is_rejected_cleanly` (15 cases), `test_installed_lock_failure_leaves_no_partial_project`, `test_installed_non_empty_destination_is_preserved` (CF-14.03) |
| 220 (cutover-specific slice) | The no-engine boundary, re-asserted at this suite's own `update` route | `test_boundary_missing_engine_update_fails_closed_at_exit_3`; `test_boundary_incompatible_engine_via_engine_source_writes_nothing` (a real `--engine-source` override at a genuinely out-of-range pin, through an installed console for the first time) |
| 220 (pre-existing, mapped not repeated) | The out-of-range/no-engine boundary at `new` and `doctor` | `tests/test_e2e_installed_rollout.py::test_out_of_range_engine_is_rejected_before_any_write`, `test_out_of_range_engine_is_visible_in_doctor`, `test_engineless_new_fails_closed_at_exit_3`, `test_engineless_doctor_json_reports_the_absent_engine` (CF-14.03) |
| 221 | Diagnostics never echo raw argv/stdout/stderr/source/ref; source secrets are stripped | `tests/test_cli.py::test_new_legacy_credential_bearing_template_url_is_rejected`, `test_update_legacy_revalidates_the_recorded_credential_bearing_src_path` (renamed by CF-18.06 so `-k credential` selects them); `tests/test_runner.py::test_scaffold_process_failure_hides_credentials_and_process_output` |
| 228 | The installed candidate console covers default generation, overrides, engine updates, legacy updates and the preview-project transition | Every test named above, plus CF-18.05's own `test_legacy_generation_and_update_against_a_local_tagged_template` and `test_preview_era_project_transition_is_rejected` |
| 229 | Migration, legacy-support, rollback and user-guide recipes are updated and exercised; diagnostic fields and statuses stay stable | `test_recipe_diagnose_with_doctor`, `test_recipe_rollback_restores_a_bad_update`, `test_recipe_pin_back_to_0_3_x`; the preview-project regeneration recipe is CF-18.05's own `test_preview_era_project_transition_is_rejected`; `uv run poe docs:build` builds the rewritten `docs/user-guide/` including the new `migration.md` |

## A real defect this issue found and fixed

Building the `--engine-source` boundary test (row 219/220) against a real,
genuinely out-of-range `forge-template` release surfaced a bug predating
CF-18.06: `_engine_worker.py`'s `info` operation read `EngineInfo.metadata_version`
unconditionally, and that attribute postdates the `0.5.0` cutover
(`engine.py`'s own docstring) — a provisioned engine old enough to lack it
crashed the worker call itself, which `engine_source.py` then reported as a
generic `EngineSourceError` at exit `1` rather than the documented
compatibility-class exit `3`. Fixed with the same `getattr` fallback
`cli.py`'s own `doctor` negotiation already uses for exactly this reason.
Regression coverage: `tests/test_engine_source.py::test_worker_info_degrades_a_too_old_engine_missing_metadata_version`
(fast suite, a minimal stand-in `forge_template` module) and
`tests/test_e2e_installed_cutover.py::test_boundary_incompatible_engine_via_engine_source_writes_nothing`
(a real `forge-template==0.3.0`).

## The `-k "credential or secret"` selector fix

Row 221's evidence command names `tests/test_cli.py tests/test_runner.py`,
but before this issue, `-k "credential or secret"` selected nothing from
`tests/test_cli.py` — the two tests actually proving credential rejection
there were named for what they call, not what they guard against. CF-18.06
renamed `test_new_legacy_template_url_is_source_validated` to
`test_new_legacy_credential_bearing_template_url_is_rejected` and
`test_update_legacy_revalidates_the_recorded_src_path` to
`test_update_legacy_revalidates_the_recorded_credential_bearing_src_path` —
no behaviour changed, only the names now say what they test.

## CI

`.github/workflows/ci.yml`'s `e2e-windows` job gained a third step running
`tests/test_e2e_installed_cutover.py -k "install_modes or legacy"` on
`windows-latest` — `uv tool install`'s produced console script and the
legacy Copier route's own file handling are the same OS-sensitivity class
CF-18.03/18.04 already added this job for. No change to the `e2e` job's
runner or Python matrix; the rest of the supported Python window is the
`test` CI matrix (3.11-3.14) and `floor` job.

## Recorded validation

To be filled in after a real CI run on the PR that lands this record, per
CONTRIBUTING's rule against a success claim based solely on local-green
tests:

| Command | Result |
| --- | --- |
| `uv run poe check` | |
| `uv run pytest tests/test_e2e_installed_cutover.py -k install_modes` | |
| `uv run pytest tests/test_e2e_installed_cutover.py -k "incompatible or invalid or failure"` | |
| `uv run pytest tests/test_e2e_installed_cutover.py -k boundary` | |
| `uv run pytest tests/test_cli.py tests/test_runner.py -k "credential or secret"` | |
| `uv run poe test:e2e` | |
| `uv run poe docs:build` | |
| CI `e2e-windows` job | |

## Boundaries retained

This is an E2E test, one worker-module bugfix, a CI step, and a
documentation change: no shipped CLI flag, protocol, component identifier,
or default path changed. `create-forge` stayed on the `0.3.x` line until
[CF-18.07](https://github.com/Sandsy09/create-forge/issues/164) (ADR 0049)
tagged and published `0.4.0`; see
[docs/release-0-4-0-validation.md](release-0-4-0-validation.md) for that
publication's own evidence.

When this boundary or its evidence changes, update this record, the
[end-to-end tests contract](end-to-end-tests.md), and the executable suite
in the same pull request.
