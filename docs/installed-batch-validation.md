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

CF-29.02 ships as two pull requests under one issue. This record states which
one delivers each row; rows marked **second pull request** are decided in the
ADR and not yet implemented when only the first has merged.

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
| AC-1 (installation modes) | **second pull request**: `uvx`, `uv tool install`, `pip install`, the `[legacy]` extra, and `--engine-source` at immutable tags |
| AC-2: invalid options, incompatible providers, destination conflicts and lock failures leave no partial project or staging state | `test_previous_provider_line_is_rejected_before_any_write` (a real `0.6.0`, exit `3`) and `test_previous_provider_line_fails_doctor_not_just_new` (exit `1`, negotiation still passing); `test_installed_batch_selection_failure_is_rejected_cleanly` over four invalid selections, including an undeclared option; `test_installed_non_empty_destination_is_preserved`; `test_installed_lock_failure_leaves_no_partial_project` (a real failure, `uv` absent from `PATH`); `test_legacy_route_cannot_select_batch` |
| AC-3: engine-native update, containment and recovery, local-data preservation; existing archetype and legacy coverage retained | **second pull request**: batch update cases and the released-client comparison. The existing modules are unchanged by the first |
| AC-4: Windows, non-UTF-8 and Linux under the accepted support policy | Linux: the full module runs in the existing `e2e` job. **Second pull request**: batch cases in the encoding suite and the Windows `e2e-windows` list |
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
