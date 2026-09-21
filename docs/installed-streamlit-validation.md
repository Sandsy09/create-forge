# Installed Streamlit Validation

This is the living evidence record for
[CF-21.02 / #166](https://github.com/Sandsy09/create-forge/issues/166): the
create-forge candidate wheel and the published `forge-template 0.6.0` engine
generate and validate the Streamlit archetype through the real installed console
script. The decision is accepted under
[ADR 0051](adr/0051-validate-installed-streamlit-generation.md).

It extends [ADR 0050](adr/0050-adopt-the-0-6-streamlit-provider-line.md)'s
in-process proof of generic selection to the installed boundary, in the same way
[installed-data-science-validation.md](installed-data-science-validation.md)
extended the Data Science preview. The provider owns the archetype's own
evidence; this repository owns the installed client, filesystem, lock, and CLI
path, and **links** the provider's records rather than restating them.

## Installed pair

`tests/test_e2e_installed_streamlit.py` builds a fresh
`create_forge-0.4.0-py3-none-any.whl` and installs it, with
`forge-template==0.6.0` pinned alongside it (`tests/conftest.py`'s session
`installed_client` fixture), into a temporary Python 3.13 virtual environment.
The environment's own `uv` is first on the subprocess `PATH`; `VIRTUAL_ENV`,
`UV_PROJECT_ENVIRONMENT`, `PYTHONHOME`, `PYTHONPATH`, user configuration, and
`FORGE_*` overrides are removed from the generation boundary. A second
environment forces in a real `forge-template 0.5.0` to model an incompatible
provider.

## Composition and Python matrix

| Composition | Python | Validation |
| --- | --- | --- |
| `streamlit` | 3.13 default | repeated installed-console generation, byte-identical output, ownership-plan and lock audit, locked restoration, canonical check, bounded smoke |
| `streamlit` + `jupyter` | 3.13 default | the same |
| `streamlit` + `scientific-python` | 3.13 default | the same |
| `streamlit` + `jupyter` + `scientific-python` | 3.13 default | the same |
| `streamlit` + `jupyter` + `scientific-python` | 3.11 and 3.14 | installed-console generation, current lock, ownership plan, restoration, canonical check, bounded smoke |

The four selections are those the provider's
[acceptance contract](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-compatibility-and-acceptance.md#valid-and-invalid-selections)
accepts. The provider proves each of them at 3.11 and 3.14 itself; the client
repeats only the heaviest, because the one real Streamlit defect the provider
found was interpreter-dependent and the client's lock finalisation must hold at
both edges too.

## What the executable evidence proves

| Criterion | Evidence |
| --- | --- |
| CF-ROADMAP-02-AC-04: installed-console E2E covers the accepted combinations, committed lock state, canonical generated checks and the bounded smoke | `test_installed_console_validates_streamlit_composition`, parametrised over the four compositions; `test_full_streamlit_composition_passes_python_window_edge` at 3.11 and 3.14. Each restores with `uv sync --all-groups --locked`, then runs `uv run --locked poe check` and `uv run --locked pytest tests/test_app.py`, both under the provider's 600-second bound, where a timeout fails and is never retried |
| CF-ROADMAP-02-AC-05: incompatible providers, invalid selections, lock failures and destination conflicts leave no partial project or staging state | `test_previous_provider_line_is_rejected_before_any_write` (a real `0.5.0`, exit `3`) and `test_previous_provider_line_is_visible_in_doctor`; `test_installed_streamlit_selection_failure_is_rejected_cleanly` over four invalid selections; `test_installed_non_empty_destination_is_preserved`; `test_installed_lock_failure_leaves_no_partial_project` (a real failure, `uv` absent from `PATH`) |
| CF-ROADMAP-02-AC-02 (installed half): Streamlit is selectable through the generic archetype/component contract | every composition test generates with `--archetype streamlit --yes`; `test_installed_list_shows_streamlit_from_discovery`. Interactive selection is proven in-process by CF-21.01's `tests/test_streamlit_adoption.py::test_an_interactive_run_offers_and_selects_streamlit` against the real `0.6.0` engine |
| CF-ROADMAP-02-AC-06: existing Library, CLI Application, Data Science and supported Copier workflows remain green | the existing modules are **unchanged**: `tests/test_e2e_engine_generation.py`, `tests/test_e2e_installed_data_science.py`, `tests/test_e2e_installed_rollout.py`, `tests/test_e2e_installed_cutover.py`, `tests/test_e2e_generation.py`; their results are recorded below |
| CF-ROADMAP-02-AC-07: user documentation explains the Streamlit recipe and links, rather than duplicates, generated-project detail | `docs/user-guide/streamlit.md`; `test_documented_recipe_runs_through_the_installed_console` runs each documented command; `tests/test_user_guide_recipes.py` keeps the guide and those commands in step, checks the provider link and the page's relative links |
| CF-ROADMAP-02-EX-01: no Streamlit content or validation in `create-forge` | no change under `src/`; `tests/test_archetype_parity.py::test_no_production_module_hardcodes_streamlit` (CF-21.01) still holds; the suite asserts no provider-owned artefact detail |

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

## Provider-owned evidence, linked and not repeated

| Concern | Owner and record |
| --- | --- |
| Wheel and sdist contents; the launcher, `.streamlit/config.toml` and `secrets.toml` staying out of them | forge-template FT-20.03: [package build and install requirements](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-compatibility-and-acceptance.md#package-build-and-install-requirements) |
| The `run` task and its exclusion from `check`; configuration and secret safeguards | the [archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-archetype.md#run-and-check-tasks) |
| The 10-second per-run and 600-second whole-check bounds, and the no-server rule | the [time-bounded, non-serving smoke](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-compatibility-and-acceptance.md#time-bounded-non-serving-smoke) contract |
| The listen guard and the generated-project endpoint matrix | forge-template's [Streamlit validation](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-validation.md) record |
| The published `0.6.0` artefacts and their audit | forge-template's [provider release record](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-provider-release.md) |

## Recorded validation

The completed CF-21.02 implementation was validated on Windows on 2026-09-21,
on `main` at `c9a33cc` (CF-21.01, [#186](https://github.com/Sandsy09/create-forge/pull/186))
plus this change, with a `create_forge-0.4.0` candidate wheel, the published
`forge-template 0.6.0`, Python 3.13.1, and the host `uv 0.12.5` building the
wheel (the candidate environment resolves its own `uv` within `>=0.12,<0.13`).
Local runs used `PYTHONUTF8=1`; see the note below the table.

| Command | Result |
| --- | --- |
| `uv run pytest tests/test_e2e_installed_streamlit.py -k "list or selection_failure or non_empty or lock_failure or previous_provider"` | 9 passed in 37.36s |
| `uv run pytest tests/test_e2e_installed_streamlit.py -k "validates_streamlit_composition or window_edge"` | 6 passed in 687.02s (11:27): `alone` 93s, `jupyter` 105s, `scientific-python` 119s, `jupyter-scientific-python` 108s, Python 3.11 edge 120s, Python 3.14 edge 137s |
| `uv run pytest tests/test_e2e_installed_streamlit.py -k recipe` | 2 passed in 141.68s: `plain` 58s, `scientific-python` 77s |
| `uv run pytest -m "not network and not e2e"` | 914 passed, 1 skipped, 119 deselected |
| `uv run pytest -m network` | 8 passed, 1026 deselected |
| `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy` | clean |
| `uv run poe check:adr`, `check:workflows`, `check:wheel` | passed; the fresh `0.4.0` wheel contains `create_forge/templates.toml` |
| `uv run poe docs:build` (strict) | passed; `site/streamlit` was absent, so the then-excluded page was not published (published by CF-21.03) |
| `uv run pre-commit run --files <changed files>` | every hook passed, including markdownlint on the new pages |

The new suite is 17 tests, all passing across the three invocations above.

**Not completed locally: a full `uv run poe test:e2e`.** The 111-test run was
stopped by the development environment for low system memory before any test
reported, so no local result exists for the existing modules against this change.
That is a gap in the local evidence, not a result. The existing e2e modules are
unchanged and the only shared edit is a keyword-only `timeout` on
`tests/installed_client.py::run` that defaults to its previous value, so the
protected CI `e2e` and `e2e-windows` jobs on the pull request are the evidence
for CF-ROADMAP-02-AC-06 and for the new suite's CI runtime. The last complete
local e2e run, on the CF-21.01 branch (`8427948`, merged as `c9a33cc`), had 90
passing and four failing on this machine's console encoding, all four passing
with `PYTHONUTF8=1`.

**Local Windows console encoding.** Without `PYTHONUTF8=1`, five existing test
cases (one in the fast suite, four in e2e) fail on a `cp1252` decode error in the
tests' own `text=True` output capture, leaving `stdout`/`stderr` as `None`. The
fast-suite case fails identically on a clean `main`; CI is unaffected. It is not
addressed here.

## Boundaries retained

This is an E2E test and documentation change only: it changes nothing under
`src/`, no CLI surface, adapter, dependency, protocol, lock, template registry, or
generated byte, and it edits none of the existing e2e modules. The Streamlit guide
page was written and tested here but **excluded from the published site** while
published `create-forge 0.4.0` could not select Streamlit.

CF-21.03 ([#167](https://github.com/Sandsy09/create-forge/issues/167), ADR 0056)
inherited the release and has done it: `create-forge 0.5.0` is published, the
exclusion is removed, and the nav entry, the `projects.md` archetype row, the
`site_description`, `installation.md` and `reference.md` are updated. This suite
was then run, unchanged, against the wheel PyPI serves
([release-0-5-0-validation.md](release-0-5-0-validation.md)). Interactive
selection at the installed level is proven through discovery and in-process, not
through a pseudo-terminal (ADR 0051 decision 6).

## One candidate, two installed suites

CF-21.03's release criteria require the exact candidate hashes for **both** this
suite and the installed update-safety suite
([update-safety-validation.md](update-safety-validation.md), CF-22.03, ADR 0054).
They run against the same candidate wheel and the same published `forge-template`
in one protected CI run, and `uv run poe evidence:candidate` prints the artefact
hashes both records bind to; the release-prerequisite checklist in that record
covers both. This suite's own protected CI run, for the merge that added it, was
[35582899643](https://github.com/Sandsy09/create-forge/actions/runs/35582899643)
(`End-to-end generation` 7m0s, `End-to-end lifecycle and update (Windows)` 2m26s)
— the CI evidence for CF-ROADMAP-02-AC-06 that the "Not completed locally" note
above points to.

When this installed boundary or its evidence changes, update this record, the
[end-to-end tests contract](end-to-end-tests.md), and the executable suite in the
same pull request.
