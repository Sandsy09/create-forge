# create-forge 0.4.0 Release Validation

This is the living evidence record for
[CF-18.07 / #164](https://github.com/Sandsy09/create-forge/issues/164), the
seventh and last child of
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153): it
publishes create-forge `0.4.0`, verifies the released `create-forge` /
`forge-template 0.5.0` pair against its own artefacts, and closes the
Engine-Default Cutover roadmap. The decision is accepted under
[ADR 0049](adr/0049-publish-0-4-0-and-close-roadmap-v3.md).

`0.4.0` is the cutover release: the `forge-template` engine is the default,
required `new` architecture; `copier` is the optional `legacy` extra; the
removed `--engine-preview` flag no longer exists. It is a **breaking**
release — the default `new` behaviour and the resolved dependency set both
change from `0.3.x`.

## Release identity

| Field | Value |
| --- | --- |
| Tag | `v0.4.0` (annotated `7e12373398c5083c30525cad3b29497886516e36`) |
| Source commit | `553af92f312e4e0cf18720ca74d2029af0885cc4` — `chore: bump to 0.4.0 and reconcile pre-cutover documentation (CF-18.07)` (#179), `main` |
| GitHub release | <https://github.com/Sandsy09/create-forge/releases/tag/v0.4.0> (published 2026-09-14) |
| PyPI project | <https://pypi.org/project/create-forge/0.4.0/> |
| wheel | `create_forge-0.4.0-py3-none-any.whl` — `sha256:4a2b56179537d1217bb26150e1e5b49f742920cbaae9f6a02db8894bf7dd5f09` |
| sdist | `create_forge-0.4.0.tar.gz` — `sha256:86724eb07b7156c407c3b78c2f876944c09bfdb37cabf4d14fd0ff97f65f6bd6` |
| Release workflow run | [34879449055](https://github.com/Sandsy09/create-forge/actions/runs/34879449055) — `release` and `Publish to PyPI` both green |
| Dry run (preceding) | [34877980428](https://github.com/Sandsy09/create-forge/actions/runs/34877980428) — computed `v0.4.0`, changelog gate, `check:wheel`, tag/release/publish all correctly skipped |

The tag points at the current tip of `main`; the release published from the
same commit. Both PyPI artefacts and the tagged GitHub release were created by
`.github/workflows/release.yml` (Trusted Publishing, `pypi` environment).

The generated release notes (`git-cliff --tag v0.4.0`) name every CF-18.01–
CF-18.06 PR; a **Breaking change** section was prepended via `gh release edit`
naming the default-path flip and pointing at the migration guide, since
git-cliff's own `chore`-filtering commit parsers do not surface it and ADR
0042 requires the release PR/notes to carry it explicitly.

## Compatibility

- **Default path is the engine.** `create-forge new` discovers the catalogue
  from `forge_template.get_engine_info()`, constructs a ProjectSpec, and
  renders through its public facade — no template repository to clone.
- **`forge-template>=0.5,<0.6`** is a required dependency of plain
  `create-forge`, not an extra. `copier<10,>=9.16` moved to the optional
  `legacy` extra (`create-forge[legacy]`).
- Against `forge-template 0.5.0`, engine discovery returns the `library`,
  `cli`, and `data-science` archetypes and the `jupyter` and
  `scientific-python` capabilities.
- `create-forge 0.3.x` remains installable and supported for at least 90 days
  and at least one further tagged release past this publication
  ([docs/engine-cutover-acceptance.md § Rollback and support
  windows](engine-cutover-acceptance.md#rollback-and-support-windows)).

## Published-artefact verification

Every command ran against the **published** `0.4.0`, not a local build, on
Windows on 2026-09-14, in throwaway virtual environments. The load-bearing
excerpts follow.

### 1. Tag, release, and source commit agree

```
$ git ls-remote --tags https://github.com/Sandsy09/create-forge.git v0.4.0^{}
553af92f312e4e0cf18720ca74d2029af0885cc4  refs/tags/v0.4.0^{}

origin/main tip:       553af92f312e4e0cf18720ca74d2029af0885cc4
gh release view v0.4.0 -> {"tagName":"v0.4.0","targetCommitish":"main","publishedAt":"2026-09-14T18:13:18Z"}
```

### 2. PyPI artefacts and dependency metadata

```
files: [('bdist_wheel', 'create_forge-0.4.0-py3-none-any.whl'),
        ('sdist', 'create_forge-0.4.0.tar.gz')]
requires_python: >=3.11
requires_dist:
   forge-template<0.6,>=0.5
   pydantic>=2.10
   pyyaml>=6.0
   questionary>=2.0
   rich>=13.9
   typer>=0.16
   uv<0.13,>=0.12
   copier<10,>=9.16; extra == "legacy"
   platformdirs>=4.3.6; extra == "legacy"
```

`forge-template` resolves as a plain dependency; `copier` and its
`platformdirs` companion carry `extra == "legacy"` — exactly the ADR 0040
adoption this release publishes.

### 3. `templates.toml` ships in the published wheel

```
$ python -c "import zipfile; print([n for n in
    zipfile.ZipFile('published-0.4.0.whl').namelist() if n.endswith('templates.toml')])"
['create_forge/templates.toml']
```

Downloaded from the PyPI wheel URL — CLAUDE.md invariant 5 against the real
artefact.

### 4. The four contractual install modes

`uvx --from "create-forge==0.4.0" create-forge doctor --json` (isolated,
`UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` for the `uv tool install` mode):

```
create-forge 0.4.0 | forge-template 0.5.0 | uv 0.12.13

$ doctor --json -> integration.line: "v0.4.x-engine"
                    integration.engine_package: "0.5.0"
                    integration.engine_range: "forge-template>=0.5,<0.6"
                    integration.copier: null (plain mode) / present (legacy mode)
```

| Install mode | `--version` | `list` | `doctor --json` |
| --- | --- | --- | --- |
| `uvx --from "create-forge==0.4.0"` | `0` → `0.4.0` | `0` (14 components: 3 archetypes, 10 capabilities, 1 platform) | `0`, fields above |
| `uv tool install "create-forge==0.4.0"` | `0` → `0.4.0` | `0` | `0` |
| `pip install "create-forge==0.4.0"` (clean venv) | `0` → `0.4.0` | `0` | `0`, `integration.line: "v0.4.x-engine"` |
| `pip install "create-forge[legacy]==0.4.0"` (clean venv) | `0` → `0.4.0` | `0` | `0` |

### 5. Engine generation of every archetype

A clean environment with published `create-forge==0.4.0` (`uvx --from`):

| Generation (`new`) | `new` | Generated `uv run --locked poe check` | `.forge/generation.json` / `uv.lock` / Git |
| --- | --- | --- | --- |
| `--archetype library --data license=mit` | `0` | `0` (`ruff format`/`check`, `mypy`, `pytest` 1 passed) | present / present / initial commit |
| `--archetype cli --data license=mit` | `0` | `0` (`mypy`, `pytest` 6 passed) | present / present / initial commit |
| `--archetype data-science --capability jupyter --data license=mit` | `0` | `0` (`pytest` 1 passed + `check_notebooks.py`) | present / present / initial commit |

Byte-for-byte generation is proven on the identical wheel by
`tests/test_e2e_installed_cutover.py` and `tests/test_e2e_installed_rollout.py`;
this run confirms the PyPI-resolved artefact behaves the same.

### 6. The `--legacy` Copier route and an engine-native update round-trip

`create-forge[legacy]==0.4.0`, `new --legacy --template library --data
license=mit`:

```
[main cd3d6c3] chore: add lockfile                       (uv.lock)
pre-commit installed at .git\hooks\pre-commit
pre-commit installed at .git\hooks\commit-msg
.copier-answers.yml present
$ uv run poe check   ->   [exit 0]  (1 passed, coverage 100%)
```

Engine-native `update --dry-run` against the published-generated library
project (through `uv tool install create-forge==0.4.0`):

```
$ create-forge update --dry-run lib-smoke
13 unchanged target(s).
Dry run complete. No project files changed.
```

(No upstream drift, since generation and update both ran against the same
`forge-template 0.5.0` release — this proves the round-trip classifies
cleanly, matching `tests/test_update_engine.py`'s no-op-update case.)

### 7. `uvx`, and the `0.3.2` pin-back

```
$ uvx --from "create-forge==0.4.0" create-forge --version
0.4.0

$ uv tool install "create-forge==0.3.2"
Installed 1 executable: create-forge
$ create-forge --version
0.3.2
$ create-forge new "Smoke Pinback" --yes --path pinback-smoke
[new exit 0]   ->   project generated, pre-commit installed
```

The `0.3.x` support-window path still resolves, installs, and generates
after `0.4.0` publishes.

### Documentation deployment

```
$ gh run list --workflow=docs.yml --branch=main
completed  success  553af92f312e4e0cf18720ca74d2029af0885cc4  (the release commit)

$ curl -s -o /dev/null -w '%{http_code}' https://sandsy09.github.io/create-forge/            -> 200
$ curl -s -o /dev/null -w '%{http_code}' https://sandsy09.github.io/create-forge/installation/ -> 200
$ curl -s -o /dev/null -w '%{http_code}' https://sandsy09.github.io/create-forge/updates/      -> 200
$ curl -s -o /dev/null -w '%{http_code}' https://sandsy09.github.io/create-forge/migration/    -> 200
$ curl -s https://sandsy09.github.io/create-forge/reference/ | grep -o "Engine-Default Cutover has shipped"
Engine-Default Cutover has shipped
$ curl -s https://sandsy09.github.io/create-forge/ | grep -o "create-forge 0.4.0 and later"
create-forge 0.4.0 and later
```

## Roadmap reconciliation

The Engine-Default Cutover roadmap is 5 epics and 21 children across two
repositories, plus the shared review obligations
**CF-ROADMAP-01-AC-06** and **CF-ROADMAP-01-AC-07**
([docs/roadmap-v3/TRACEABILITY.md](roadmap-v3/TRACEABILITY.md)). At `0.4.0`
every `create-forge`-owned child has landed evidence and is closed, and the
paired provider evidence
([FT-18.01](https://github.com/Sandsy09/forge-template/issues/156)) closed
first, satisfying release-sequencing gate 5.

| Epic | Children | Status |
| --- | --- | --- |
| CF-EPIC-16 / create-forge#152 | 3 | closed — ADR 0040/0041/0042, contract-only |
| CF-EPIC-18 / create-forge#153 | 7 | closed — this record |
| FT-EPIC-17 / forge-template#142 | — | closed — reviewed `forge-template 0.5.0` published |
| FT-EPIC-18 / forge-template#143 | FT-18.01 (forge-template#156) | FT-18.01 closed — integrated cutover validation against the released client candidate; the epic itself is `forge-template`'s own to close |

### CF-EPIC-18 acceptance

| Criterion | Discharged by |
| --- | --- |
| The engine is the default, required `new` path; `copier` is the optional `legacy` extra | ADR 0040; CF-18.01 |
| `--engine-source`/`--engine-ref` provision an isolated environment | ADR 0044; CF-18.02 |
| The engine `new` Git/hook lifecycle and `.forge/generation.json` | ADR 0045; CF-18.03 |
| Engine-native `update` dispatch | ADR 0046; CF-18.04 |
| The legacy Copier route and preview-project transition | ADR 0047; CF-18.05 |
| The installed-console acceptance matrix and rewritten user guide | ADR 0048; CF-18.06 |
| Publication, verification, and roadmap close-out | this record; CF-18.07, ADR 0049 |

### Review obligations

| Criterion | Discharged by |
| --- | --- |
| **CF-ROADMAP-01-AC-06** — implementation, migration E2E, legacy regression and release tasks filed separately with an explicit dependency graph | CF-16.03, CF-18.06, CF-18.07 — all merged/published |
| **CF-ROADMAP-01-AC-07** — cutover cannot ship until the reviewed provider release and full cross-repository matrix pass together | FT-18.01 closed before this publication (checks 1–7 above ran only after) |

`docs/roadmap-v3/github-issues/filing-manifest.json`, the 24 filed issue
bodies, `ISSUE-INDEX.md`, and `scripts/check_roadmaps.py` stay unchanged by
this closure — the checker has no "complete" pack status, so completion is
recorded here and in the roadmap-v3 Status prose instead, matching ADR 0049
decision 5. `python scripts/check_roadmaps.py` continues to report
`Roadmaps valid: 8 epics, 30 children, 45 review obligations; filed-open;
links and DAG OK.`

The CF-EPIC-18 / Stage 18 create-forge milestone closes with this record; the
roadmap-v3 pack's own filing status remains `filed-open` by design (see
above).

## Boundaries retained

No shipped module, dependency range, CLI flag, protocol, component
identifier, or default path changed in this release beyond what CF-18.01–
CF-18.06 already merged to `main`. `create-forge 0.4.0` is the release that
publishes them. Whether a later release promotes the engine to `1.0.0`, and
whether `template/` is ever retired in favour of the catalogue, remain
explicitly later decisions.

When a later create-forge release is published, add its own record rather
than editing this one.
