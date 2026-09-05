# create-forge 0.3.0 Release Validation

This is the living evidence record for
[CF-14.04 / #114](https://github.com/Sandsy09/create-forge/issues/114), the
last child of
[CF-EPIC-14](https://github.com/Sandsy09/create-forge/issues/104): it publishes
create-forge `0.3.0`, verifies the released
`create-forge` / `forge-template 0.4.1` pair against its own artefacts, and
closes the Data Science roadmap. The decision is accepted under
[ADR 0034](adr/0034-publish-0-3-0-and-close-roadmap-v2.md).

`0.3.0` is the first create-forge line with discovery-driven generic component
selection and the Data Science archetype reachable behind `--engine-preview`.
The default `new` command is unchanged — it still renders directly from Copier
— and `--engine-preview` stays hidden and opt-in. This release is not the CLI
cutover.

## Release identity

| Field | Value |
| --- | --- |
| Tag | `v0.3.0` (annotated `4301653f2a3fa21f65b1014072c04b45f8d8821d`) |
| Source commit | `d34652801a73f0d1231c3ca984e367ac1e52babd` — `chore: generate the 0.3.0 changelog (#129)`, `main` |
| GitHub release | <https://github.com/Sandsy09/create-forge/releases/tag/v0.3.0> (published 2026-09-05) |
| PyPI project | <https://pypi.org/project/create-forge/0.3.0/> |
| wheel | `create_forge-0.3.0-py3-none-any.whl` — `sha256:b6cbf938f4fbfb327940de32d9ecc686d31b8c0535897954a18f85255897baaf` |
| sdist | `create_forge-0.3.0.tar.gz` — `sha256:f52a544f2b6a6c872a1896e4f4c745b8b83f38ef6a304905371c3b97686a1461` |

The tag points at the current tip of `main`; the release published from the
same commit. Both PyPI artefacts and the tagged GitHub release were created by
`.github/workflows/release.yml` (Trusted Publishing, `pypi` environment) in run
[33983037941](https://github.com/Sandsy09/create-forge/actions/runs/33983037941),
`release` and `Publish to PyPI` both green.

## Compatibility

- **Default path unchanged.** `create-forge new` renders from the bundled
  `forge-template` Copier registry and needs no engine.
- **`create-forge[engine]`** resolves `forge-template>=0.4.1,<0.5` and
  `uv>=0.12,<0.13`. Neither is a plain dependency; both carry
  `extra == "engine"`. `--engine-preview` remains hidden and dev-only.
- Against `forge-template 0.4.1`, `--engine-preview` discovery returns five
  components: the `library`, `cli`, and `data-science` archetypes and the
  `jupyter` and `scientific-python` capabilities.

## Published-artefact verification

Every command ran against the **published** `0.3.0`, not a local build, on
Windows on 2026-09-05, in throwaway virtual environments. The load-bearing
excerpts follow.

### 1. Tag, release, and source commit agree

```
$ git ls-remote --tags https://github.com/Sandsy09/create-forge.git v0.3.0
4301653f2a3fa21f65b1014072c04b45f8d8821d  refs/tags/v0.3.0

tag v0.3.0 -> commit:  d34652801a73f0d1231c3ca984e367ac1e52babd
origin/main tip:       d34652801a73f0d1231c3ca984e367ac1e52babd
gh release view v0.3.0 -> {"tagName":"v0.3.0","targetCommitish":"main","publishedAt":"2026-09-05T18:07:05Z"}
```

### 2. PyPI artefacts and engine-extra metadata

```
files: [('bdist_wheel', 'create_forge-0.3.0-py3-none-any.whl'),
        ('sdist', 'create_forge-0.3.0.tar.gz')]
requires_python: >=3.11
requires_dist:
   copier<10,>=9.4
   pydantic>=2.10
   questionary>=2.0
   rich>=13.9
   typer>=0.15
   forge-template<0.5,>=0.4.1; extra == "engine"
   uv<0.13,>=0.12; extra == "engine"
```

### 3. `templates.toml` ships in the published wheel

```
$ python -c "import zipfile; print([n for n in
    zipfile.ZipFile('published.whl').namelist() if n.endswith('templates.toml')])"
['create_forge/templates.toml']
```

Downloaded from the PyPI wheel URL — CLAUDE.md invariant 5 against the real
artefact.

### 4. The engine-less command surface (`pip install create-forge`)

A clean venv with `create-forge==0.3.0` and no extra:

```
$ create-forge --version
0.3.0

$ create-forge list
ID                 Name     Description                                  Status
library (default)  Library  An installable Python package. src layout, ...

$ create-forge doctor --json   ->   integration.engine_package: None
                                    integration.engine_range: forge-template>=0.4.1,<0.5
                                    checks: Python 3.11+ ✓  git ✓  uv ✓  git identity ✓
                                            registry ✓  config ✓

$ create-forge new --engine-preview --archetype library --yes --path rej ...
The engine extra isn't installed. Run `pip install 'create-forge'` ...
[exit 1]   ->   destination not created
```

### 5. The released pair generates and checks every archetype

A clean venv with `create-forge[engine]==0.3.0`:

```
create-forge 0.3.0 | forge-template 0.4.1 | uv 0.12.10
```

| Generation (`new --engine-preview`) | `new` | Generated `uv run --locked poe check` | Forge dep in lock |
| --- | --- | --- | --- |
| `--archetype library` | `0` | `0` (mypy + `pytest` 1 passed) | none |
| `--archetype cli` | `0` | `0` (mypy + `pytest` 6 passed); `[project.scripts]` `smoke-engine-cli = "smoke_engine_cli.cli:app"` | none |
| `--archetype data-science --capability jupyter` | `0` | `0` (`pytest` 1 passed + `check_notebooks.py`) | none |
| `--archetype data-science --capability jupyter --capability scientific-python` | `0` | `0` (`pytest` 2 passed incl. `test_scientific_python` + `check_notebooks.py`) | none |

Byte-for-byte generation is proven on the identical wheel by
`tests/test_e2e_installed_data_science.py` and
`tests/test_e2e_installed_rollout.py`; this run confirms the PyPI-resolved
artefact behaves the same.

### 6. The default Copier path from an engine-less install

`create-forge new` (no `--engine-preview`) in the same engine-less venv,
against `forge-template`'s latest tag:

```
Initialized empty Git repository ... p-copier/.git/
[main (root-commit) 3dfd30a] feat: initial scaffold from template   (24 files)
[main 3d75db7] chore: add lockfile                                  (uv.lock)
pre-commit installed at .git\hooks\pre-commit
[new exit 0]
.git/  uv.lock  .copier-answers.yml  present
$ (cd p-copier && uv run poe check)   ->   [exit 0]  (1 passed, coverage 100%)
```

Both `_tasks` ran; the answers round-tripped into `.copier-answers.yml`.

### 7. `uvx` — how users actually invoke it

```
$ uvx --from "create-forge==0.3.0" create-forge --version
0.3.0

$ uvx --from "create-forge[engine]==0.3.0" create-forge new "Smoke Uvx" \
      --engine-preview --archetype library --yes --path p-uvx ...
[uvx new exit 0]   ->   project generated
```

## Roadmap reconciliation

The Data Science roadmap is six epics and 24 child issues across two
repositories. At `0.3.0` every one has landed evidence and is closed.

| Epic | Children | Status |
| --- | --- | --- |
| FT-EPIC-10 / forge-template#96 | 5 | closed — Data Science architecture contract |
| FT-EPIC-11 / forge-template#97 | 5 | closed — Jupyter (FT ADR 0050), Scientific Python (FT ADR 0051) |
| FT-EPIC-12 / forge-template#98 | 5 | closed — `forge-template 0.4.0` published |
| CF-EPIC-13 / create-forge#103 | 5 | closed — ADR 0026–0030, `--engine-preview` selection pipeline |
| FT-EPIC-14 / forge-template#99 | 4 | closed — reviewed `forge-template 0.4.1` release |
| CF-EPIC-14 / create-forge#104 | 4 | closed — ADR 0031–0034, installed validation, this release |

### CF-EPIC-14 acceptance

| Criterion | Discharged by |
| --- | --- |
| Declares and resolves the compatible engine range | ADR 0031; `pyproject.toml` `engine` extra `forge-template>=0.4.1,<0.5`; check 2 |
| Real console-script tests generate Data Science through `--engine-preview` into an empty destination | `tests/test_e2e_installed_data_science.py` (CF-14.02); check 5 |
| Generated lock verifies, canonical checks pass, notebook validation succeeds in isolation | [installed Data Science validation](installed-data-science-validation.md) (CF-14.02); check 5 |
| Library and CLI Application engine-path E2E green; default Copier path unchanged | `tests/test_e2e_installed_rollout.py` (CF-14.03); checks 5 and 6 |
| Missing/out-of-range engine, invalid selection, lock failure, destination conflict leave no partial project | CF-14.03 failure matrix; [rollout regression and failure validation](rollout-regression-validation.md); check 4 |
| Documentation, diagnostics, release notes, roadmap evidence describe the supported path | this record; the release-page Compatibility note; the Stage 14 roadmap records |
| Any required release is published and verified before the roadmap closes | this record — checks 1–7 |

Both Stage 13 and Stage 14 create-forge milestones are closed, and both
repositories' `CROSS-REPO-DEPENDENCIES.md` matrices describe the shipped graph.

## Boundaries retained

No shipped module, dependency range, CLI flag, protocol, component identifier,
or default path changed in this release beyond the version string CF-14.01
committed. `--engine-preview` is still hidden. The engine replacing direct
Copier as the default `new` path remains a separate, unfiled decision.

When a later create-forge release is published, add its own record rather than
editing this one.
