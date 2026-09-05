# Installed Data Science Validation

This is the living evidence record for
[CF-14.02 / #112](https://github.com/Sandsy09/create-forge/issues/112): the
create-forge `0.3.0` candidate wheel and published `forge-template 0.4.1`
engine generate and validate Data Science through the real installed console
script. The decision is accepted under
[ADR 0032](adr/0032-validate-installed-data-science-generation.md).

This record extends the
[Data Science preview-pipeline validation](data-science-preview-validation.md)
from an editable development console to the release-candidate installation
boundary. The provider's
[reviewed-release record](https://github.com/Sandsy09/forge-template/blob/main/docs/reviewed-engine-release.md)
owns the engine artefact audit; this repository owns the installed client,
filesystem, lock, and CLI path.

## Installed pair

`tests/test_e2e_installed_data_science.py` builds a fresh
`create_forge-0.3.0-py3-none-any.whl`, creates a temporary Python 3.13 virtual
environment, and installs:

```text
<candidate-wheel>[engine]
forge-template==0.4.1
```

The test reads the installed distributions rather than the source tree. It
asserts create-forge's PEP 610 `direct_url.json` names the candidate wheel,
forge-template has no direct-install record, both package versions are exact,
and the candidate metadata still declares `forge-template>=0.4.1,<0.5` and
`uv>=0.12,<0.13` only for the `engine` extra. The environment's own `uv` is
first on the subprocess `PATH`; `VIRTUAL_ENV`, `UV_PROJECT_ENVIRONMENT`,
`PYTHONHOME`, `PYTHONPATH`, user configuration, and `FORGE_*` overrides are
removed from the generation boundary.

## Composition and Python matrix

| Composition | Python | Validation |
| --- | --- | --- |
| `data-science` + `jupyter` | 3.13 default | repeated installed-console generation, ownership and lock audit, restore, canonical check, notebook execution, wheel/sdist build, isolated wheel install |
| `data-science` + `jupyter` + `scientific-python` | 3.13 default | the same, plus the generated Scientific Python smoke test |
| `data-science` + `jupyter` + `scientific-python` | 3.11 and 3.14 | installed-console generation, current lock, restore, canonical check, generated Scientific Python smoke test, and notebook execution |

The Python 3.11/3.14 edge pair mirrors the provider's Stage 14 handoff. The
provider continues to own broader composition and interpreter matrices.

## What the executable evidence proves

| #112 criterion | Evidence |
| --- | --- |
| Both accepted Data Science compositions pass through installed `create-forge` | `test_installed_console_validates_data_science_composition`, parametrised over the two rows above |
| Notebook and scientific-stack smoke evidence runs in isolated generated environments | `_restore_and_check` runs the generated project's locked `poe check`, explicit `notebook:check`, and the full composition's generated `tests/test_scientific_python.py`; `test_full_data_science_composition_passes_python_window_edge` repeats them at 3.11 and 3.14 |
| Generated results and locks are deterministic across repeated runs | `test_installed_console_validates_data_science_composition` compares every relative file and byte, including `uv.lock`, after two independent generations and runs `uv lock --check` on each |
| Temporary E2E resources are cleaned after success or failure | the installed-client fixture, both composition tests, and each generated-wheel install use `tempfile.TemporaryDirectory` context managers; teardown is independent of test outcome |

The same composition test also proves:

- the installed pipeline's plan and the console-written files agree byte for
  byte, with each path owned by Foundation or a selected component and every
  selected component contributing;
- initial output contains the client-owned lock but no `.git`, `.venv`, or
  surviving `.create-forge-*` staging sibling;
- generated `pyproject.toml`, `uv.lock`, wheel metadata, and the isolated
  installed environment contain neither `create-forge` nor `forge-template`;
- both wheel and sdist exclude marker content planted in the five ignored
  data, model, and artefact working trees; and
- the installed generated package imports, reports version `0.1.0` and
  `Requires-Python >=3.11`, and contains `py.typed`.

## Recorded validation

The completed CF-14.02 implementation was validated on Windows on 2026-09-05:

| Command | Result |
| --- | --- |
| `uv sync --all-groups --all-extras` | passed; 53 packages resolved and 52 checked |
| `uv run pytest tests/test_e2e_installed_data_science.py -vv` | 5 passed in 377.83s |
| `uv run poe check` | formatting, lint, and typing passed; 362 tests passed, 36 deselected |
| `uv run pytest -m network` | 8 passed, 390 deselected |
| `uv run poe test:e2e` | 28 passed, 370 deselected in 596.88s |
| `uv run poe check:wheel` | passed; the fresh `0.3.0` wheel contains `create_forge/templates.toml` |
| `uv run pre-commit run --all-files` | all configured hooks passed |
| `git diff --check` | clean |

## Boundaries retained

This is an E2E test and documentation change only. It adds no component
knowledge to a shipped module and changes no CLI surface, adapter, dependency,
protocol, lock, template registry, or generated byte. `--engine-preview`
remains hidden and opt-in. The installed Library/CLI, default Copier,
compatibility, selection, filesystem-failure, and cleanup regression matrix is
CF-14.03's, delivered in
[`tests/test_e2e_installed_rollout.py`](../tests/test_e2e_installed_rollout.py)
and recorded by the canonical
[rollout regression and failure validation](rollout-regression-validation.md).
CF-14.04 ([ADR 0034](adr/0034-publish-0-3-0-and-close-roadmap-v2.md))
published create-forge `0.3.0` and verified the released pair — the canonical
[release 0.3.0 validation](release-0-3-0-validation.md) record.

When this installed boundary or its evidence changes, update this record,
the [end-to-end tests contract](end-to-end-tests.md), and the executable suite
in the same pull request.
