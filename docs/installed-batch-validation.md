# Installed Batch Validation

This is the living evidence record for
[CF-29.02 / #205](https://github.com/Sandsy09/create-forge/issues/205): the
create-forge candidate wheel and the published `forge-template 0.7.0` engine
generate and validate the batch archetype through the real installed console
script. The decision is accepted under
[ADR 0062](adr/0062-validate-batch-through-the-installed-candidate.md).

It extends [ADR 0061](adr/0061-adopt-the-0-7-batch-provider-line.md)'s
in-process proof of generic selection to the installed boundary, in the same way
[installed-streamlit-validation.md](installed-streamlit-validation.md) extended
the Streamlit adoption. The provider owns the archetype's own evidence; this
repository owns the installed client, filesystem, lock, and CLI path, and
**links** the provider's records rather than restating them.

CF-29.02 shipped as two pull requests under one issue: the first
([#249](https://github.com/Sandsy09/create-forge/pull/249)) delivered the core
installed suite, the recipes and the guide page; the second delivered the
cross-cutting evidence (installation modes, Windows and non-UTF-8, update, and
the released-client comparison). Each row below names its evidence.

## Installed pair

`tests/test_e2e_installed_batch.py` builds a fresh
`create_forge-0.5.0-py3-none-any.whl` and installs it, with
`forge-template==0.7.0` pinned alongside it (`tests/conftest.py`'s session
`installed_client` fixture), into a temporary Python 3.13 virtual environment.
The environment's own `uv` is first on the subprocess `PATH`; `VIRTUAL_ENV`,
`UV_PROJECT_ENVIRONMENT`, `PYTHONHOME`, `PYTHONPATH`, user configuration, and
`FORGE_*` overrides are removed from the generation boundary. A second
environment forces in a real `forge-template 0.6.0` to model an incompatible
provider.

## Composition and Python matrix

| Composition | Python | Validation |
| --- | --- | --- |
| `batch` | 3.13 default | repeated installed-console generation, byte-identical output, ownership-plan and lock audit, locked restoration, canonical check, bounded smoke, the job through both entry points |
| `batch` + `jupyter` | 3.13 default | the same |
| `batch` + `scientific-python` | 3.13 default | the same |
| `batch` + `jupyter` + `scientific-python` | 3.13 default | the same |
| `batch` + `jupyter` + `scientific-python` | 3.11 and 3.14 | installed-console generation, current lock, ownership plan, restoration, canonical check, bounded smoke, the job through both entry points |

The four selections are those the provider's
[acceptance contract](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-compatibility-and-acceptance.md#valid-and-invalid-selections)
accepts and sweeps at both window edges. The catalogue accepts **640** batch
compositions in all; the client mirrors the provider's four rather than running
all 640 through an installed console, because it composes selections generically
and holds no per-composition logic. The client repeats only the heaviest at 3.11
and 3.14: batch declares no runtime dependency, so there is no third-party
resolution to fail, but the client's own lock finalisation and the generated
project's `poe check` still need proving at the floor and the ceiling.

## What the executable evidence proves

| Criterion | Evidence |
| --- | --- |
| AC-1: generic selection, lock restoration, checks and the bounded example job through the installed console | `test_installed_console_validates_batch_composition`, parametrised over the four compositions; `test_full_batch_composition_passes_python_window_edge` at 3.11 and 3.14. Each restores with `uv sync --all-groups --locked`, runs `uv run --locked poe check` and `uv run --locked pytest tests/test_job.py` under the provider's 600-second bound (a timeout fails and is never retried), then runs the job through the console script and `python -m`. Generic selection: every test generates with `--archetype batch --yes`, and `test_installed_list_shows_batch_from_discovery`. Interactive selection is proven in-process by CF-29.01's `tests/test_batch_adoption.py` against the real `0.7.0` engine |
| AC-1 (installation modes) | `test_install_modes_select_batch_generically`, parametrised over `uvx`, `uv tool install`, `pip install` and the `[legacy]` extra, each asserting the committed metadata names `batch` and the `0.7.0` provider; `test_install_modes_engine_source_at_the_released_tag_generates_batch` (the immutable public `v0.7.0` tag generates) and `test_install_modes_engine_source_at_the_previous_tag_exits_3` (`v0.6.0`: exit `3`, nothing created). The helpers gained a defaulted `archetype` argument, so the existing library cases are unchanged |
| AC-2: invalid options, incompatible providers, destination conflicts and lock failures leave no partial project or staging state | `test_previous_provider_line_is_rejected_before_any_write` (a real `0.6.0`, exit `3`) and `test_previous_provider_line_fails_doctor_not_just_new` (exit `1`, negotiation still passing); `test_installed_batch_selection_failure_is_rejected_cleanly` over four invalid selections, including an undeclared option; `test_installed_non_empty_destination_is_preserved`; `test_installed_lock_failure_leaves_no_partial_project` (a real failure, `uv` absent from `PATH`); `test_legacy_route_cannot_select_batch` |
| AC-3: engine-native update, containment and recovery, local-data preservation; existing archetype and legacy coverage retained | Update: `test_batch_no_op_update_changes_nothing`, `test_batch_update_preserves_a_local_job_edit_and_the_generated_output`, `test_batch_dry_run_writes_nothing` and `test_batch_degraded_update_applies_a_changed_job_and_keeps_the_output` in `tests/test_e2e_installed_update_safety.py`, using CF-22.03's techniques; the existing containment and recovery cases run unchanged. Existing archetypes: `test_existing_archetype_output_is_unchanged_across_the_provider_line` generates `library`, `cli`, `data-science` and `streamlit` through the **published** `create-forge 0.5.0` (on its own `0.6` engine) and through the candidate (on `0.7.0`) and finds every file byte-identical except `uv.lock` and the provider version in `.forge/generation.json`; `test_the_released_client_runs_on_the_previous_provider_line` and `test_the_released_client_does_not_know_batch` keep that honest. Legacy: the existing `--legacy` cases are unchanged and `test_legacy_route_cannot_select_batch` shows the registry stays Library-only |
| AC-4: Windows, non-UTF-8 and Linux under the accepted support policy | Linux: every module above runs in the existing `e2e` job. Windows: the `e2e-windows` job gained an "Installed batch tests" step (the `alone` composition end to end plus the ten fast tests: 11 in all), and the batch install-mode and update cases ride its existing `install_modes or legacy` selection and update-safety module; `test_batch_generation_and_job_survive_every_lane` in the encoding suite runs under the `ambient`, `utf8-off` and `utf8-on` lanes on Windows Python 3.11, 3.13 and 3.14, with a non-ASCII name and description, a CJK destination, and the job run by plain `python -m` with no sync. `tests/test_installed_batch_evidence.py` fails the fast suite if the Windows step, or the `alone` composition inside it, is dropped |
| AC-5: exact artefacts and user recipes recorded; provider specifications not duplicated | `docs/user-guide/batch.md`; `test_documented_recipe_runs_through_the_installed_console` runs each documented command, then the documented check and run; `tests/test_user_guide_recipes.py` keeps the guide and those commands in step and checks the provider link and the page's relative links. Artefacts are recorded below |
| No batch content or validation in `create-forge` | no change under `src/`; `tests/test_archetype_parity.py::test_no_production_module_hardcodes_batch` (CF-29.01) still holds; the suite asserts no provider-owned artefact detail |

The composition test also proves:

- the installed pipeline's plan and the console-written files agree byte for
  byte, each path owned by Foundation or a selected component, and every selected
  component contributing;
- initial output contains the client-owned lock and the committed
  `.forge/generation.json` but no `.venv` and no surviving `.create-forge-*`
  staging sibling;
- two independent generations are identical, including `uv.lock`, and both locks
  pass `uv lock --check`; and
- neither `create-forge` nor `forge-template` appears in the generated
  `pyproject.toml` or its lock.

The job assertions are deliberately client-level: both entry points exit `0`,
produce the output file with the sample input's record count, and agree byte for
byte. The transformation itself, its idempotency, and its fail-fast behaviour
are the provider's.

Gaps, recorded rather than hidden:

- **The real three-way merge across provider versions is not covered for
  `batch`.** `0.7.0` is the first release containing it, so there is no older
  batch render to differ from; `tests/test_update_engine.py` proves the merge for
  the archetypes that have one. The batch update cases use the digest-edit
  technique of [update-safety-validation.md](update-safety-validation.md)
  instead. A batch change in an `0.7.x` patch is the point at which the real
  merge can be exercised.
- **A local-data case uses committed edits and git-ignored output, not an
  untracked file**: an update refuses a dirty tree, so an untracked file would
  test the refusal, which the update-safety suite already covers.
- **Four of 640 compositions** is deliberate (see above).

## Provider-owned evidence, linked and not repeated

| Concern | Owner and record |
| --- | --- |
| The job's transformation, rerun, idempotency and malformed-record behaviour | the [archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-archetype.md#rerun-idempotency-and-failure-handling) |
| Wheel and sdist contents; the sample input staying out of them | forge-template FT-28.02: [package build and install requirements](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-compatibility-and-acceptance.md#package-build-and-install-requirements) |
| The 5-second per-run and 600-second whole-check bounds | the [time-bounded, deterministic smoke](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-compatibility-and-acceptance.md#time-bounded-deterministic-smoke) contract |
| The generated-project endpoint matrix at Python 3.11 and 3.14 | forge-template's [batch validation](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-validation.md) record |
| The published `0.7.0` artefacts and their audit | forge-template's [provider release record](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-provider-release.md) |
| What the archetype deliberately does not include (schedulers, queues, retries) | the archetype contract's [explicit exclusions](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-archetype.md#explicit-exclusions) |

## Recorded validation

The first CF-29.02 pull request was validated on Windows on 2026-10-09, on
`main` at `1416ec8` (CF-29.01, [#248](https://github.com/Sandsy09/create-forge/pull/248))
plus this change, with a `create_forge-0.5.0` candidate wheel, the published
`forge-template 0.7.0`, and a Python 3.13 candidate environment. Under
`uv run` the project's locked `uv 0.12.23` is first on `PATH`, so it built the
wheel and created the environments (the machine's own `uv` is 0.12.5, and the
candidate environment resolves its own `uv` within `>=0.12,<0.13`). Local runs
used `PYTHONUTF8=1`.

| Command | Result |
| --- | --- |
| `uv run pytest -m e2e tests/test_e2e_installed_batch.py -k "not composition and not window_edge and not recipe"` | 10 passed in 35.35s |
| `uv run pytest -m e2e tests/test_e2e_installed_batch.py -k "composition or window_edge or recipe"` | 8 passed in 494.38s (8:14): the four compositions, the 3.11 and 3.14 edges, and both recipes |
| `uv run poe check` | 1613 passed, 11 skipped, 188 deselected; format, lint and mypy strict clean |
| `uv run poe check:adr`, `check:workflows`, `check:wheel` | passed; the fresh `0.5.0` wheel contains `create_forge/templates.toml` |
| `uv run poe docs:build` (strict) | passed; `site/batch` was absent, so the excluded page was not published |
| `uv run poe audit` | clean in the runtime, legacy and full scopes |

The new suite is 18 tests, all passing across the two invocations above. The
11 skipped cases in the fast suite are host-specific (symlinks, POSIX
permission bits, undecodable path bytes) and unchanged.

The existing e2e modules are unchanged by this pull request. They were run in
full, module by module, against the exact `0.7.0` pair for CF-29.01
([#248](https://github.com/Sandsy09/create-forge/pull/248)): 161 passed and 1
skipped (a POSIX-only symlink case) of 162.

The second pull request was validated on the same machine on 2026-10-09, on
`main` at `6f15a9f` (the first pull request) plus this change. It edits three
existing modules and adds one, and changes nothing under `src/` or in the shared
harness, so those three were re-run **in full** and the rest stand on the runs
above.

| Command | Result |
| --- | --- |
| `uv run pytest -m e2e tests/test_e2e_installed_cutover.py` | 24 passed in 153.44s: the 18 existing cases and the 6 new ones (four install modes, `--engine-source` at `v0.7.0` and at `v0.6.0`) |
| `uv run pytest -m e2e tests/test_e2e_installed_encoding.py` | 23 passed in 72.47s, including `test_batch_generation_and_job_survive_every_lane` under `ambient`, `utf8-off` and `utf8-on`, each lane verified non-UTF-8 or the test fails |
| `uv run pytest -m e2e tests/test_e2e_installed_update_safety.py` | 18 passed, 1 skipped (POSIX-only symlinked parent) in 63.81s, including the 4 new batch cases |
| `uv run pytest -m e2e tests/test_e2e_installed_cross_line.py` | 6 passed in 40.32s: the two controls and the four archetypes |
| `uv run poe check` | 1616 passed, 11 skipped, 207 deselected; format, lint and mypy strict clean |
| `uv run poe check:adr`, `check:workflows`, `check:wheel`, strict `docs:build`, `poe audit` | passed; the batch page is still absent from the site; the audit is clean in all three scopes |

The guards added here were mutation-checked rather than assumed. Dropping the
batch module from the Windows job fails two of the three cases in
`tests/test_installed_batch_evidence.py`, and excluding the `alone` composition
from its selection fails the third; perturbing one byte of the candidate's
`README.md` makes the released-client comparison fail with `['README.md']`.

The first pull request's protected CI run
([37915766414](https://github.com/Sandsy09/create-forge/actions/runs/37915766414))
is the CI-runtime evidence for the batch suite: the Linux `e2e` job went from
about 4 minutes to 8m05s, against its 60-minute limit, and the Windows lifecycle
job took 3m17s against 45.

## Boundaries retained

This is an E2E test and documentation change only: it changes nothing under
`src/`, no CLI surface, adapter, dependency, protocol, lock, template registry, or
generated byte, and the first pull request edits none of the existing e2e
modules. The batch guide page is written and tested here but **excluded from the
published site** while published `create-forge 0.5.0` cannot select `batch`.
CF-29.03 ([#206](https://github.com/Sandsy09/create-forge/issues/206)) inherits
the release: remove the exclusion, add the nav entry and a `projects.md`
archetype row, and update `site_description`, `installation.md` and
`reference.md`. Interactive selection at the installed level is proven through
discovery and in-process, not through a pseudo-terminal (ADR 0051 decision 6,
ADR 0062 decision 6).

When this installed boundary or its evidence changes, update this record, the
[end-to-end tests contract](end-to-end-tests.md), and the executable suite in the
same pull request.
