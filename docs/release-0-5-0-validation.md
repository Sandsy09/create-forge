# create-forge 0.5.0 release validation

Records the published `create-forge 0.5.0` / `forge-template 0.6.0` pair
verified against its own artefacts, and the close-out of the Streamlit client
work (CF-21.03, [#167](https://github.com/Sandsy09/create-forge/issues/167),
[ADR 0056](adr/0056-publish-create-forge-0-5-0.md)). It follows
[release-0-4-0-validation.md](release-0-4-0-validation.md)'s shape. Everything
below was measured on 2026-09-21 against what PyPI serves, not against the
working tree, except where a row says otherwise. The output is verbatim where it
is quoted and summarised where it says so.

Nothing here claims an engine cutover: `0.5.0` is a compatibility-line crossing
to the `forge-template 0.6` provider line (a fifteenth component, the `streamlit`
archetype), with no protocol, `metadata_version` or facade change.

## Release identity

| Fact | Value |
| --- | --- |
| Release commit | `261d8151871c68ccd6b33089db3b4adeaa01db3a` (PR [#216](https://github.com/Sandsy09/create-forge/pull/216), squash of Phase A) |
| Tag | `v0.5.0`, annotated (`e55e88ea…`), **dereferences to the release commit** |
| Protected CI on the release commit | [run 35659447799](https://github.com/Sandsy09/create-forge/actions/runs/35659447799), all 13 checks passed |
| Dry run | [run 35662069026](https://github.com/Sandsy09/create-forge/actions/runs/35662069026), `headSha` equal to the release commit; created no tag, release or upload |
| Real release | [run 35662218487](https://github.com/Sandsy09/create-forge/actions/runs/35662218487), `headSha` equal to the release commit; `release` and `Publish to PyPI` both succeeded |
| GitHub release | [v0.5.0](https://github.com/Sandsy09/create-forge/releases/tag/v0.5.0), not a draft, not a pre-release, published 2026-09-21T22:21:27Z |
| PyPI | `create-forge 0.5.0`, latest; wheel uploaded 22:21:55Z, sdist 22:21:57Z |
| Dispatch authority | The real dispatch was made only after the maintainer's explicit go, after the dry run and after re-checking that `main` had not moved (ADR 0056 decision 4) |

The dry run printed no commit; its run's `headSha` was read and compared with the
commit whose CI had passed, and `main` was re-read immediately before the real
dispatch.

## Published artefacts

| File | Size | Archive sha256 (PyPI) | Content digest |
| --- | --- | --- | --- |
| `create_forge-0.5.0-py3-none-any.whl` | 98744 | `445a7dbeb5d4bcfaac379551d09052f1ebe17aba0c8fcfbf1c31bd8c667bafaa` | `sha256:de444e16669a034be297b81e1617894846d4c24a0ba6da0c4333da7f5d1c36a6` |
| `create_forge-0.5.0.tar.gz` | 290791 | `800081c1863eabbeb57db8e8d2dddf8827ff7cc2d340b78e6e3b45a31274dd50` | `sha256:0906b670451da138889d3106eb9f00f5e66d16d5c49d8282d6ab8e2a1da62d54` |

Bound to the candidate by `uv run poe evidence:candidate` on the clean release
commit and `scripts/candidate_evidence.py --archive` on the downloaded files
(ADR 0054's content-digest rule):

- The **wheel content digest is identical** to the candidate's, so the published
  wheel is byte-for-byte the same members the protected CI validated.
- The **wheel archive sha256 differs** (candidate build on the maintainer's
  Windows host `a89cff60c6c6b8aecc0152576602148741e900ff1bfc74ec3dc2770f39b398da`
  against PyPI's `445a7dbe…`). This is the build-environment effect ADR 0054
  documents (identical members, different compressed stream), not a difference
  in what shipped.
- The **sdist archive sha256 and content digest both match** the local build.
- Members of the published wheel that differ from the last recorded candidate
  (`f538d21`, `0.4.0` packaging): `METADATA` (the version), `RECORD` and
  `create_forge/compat.py` (`INTEGRATION_LINE`). Nothing in the update-safety
  source set changed.
- `create_forge/templates.toml` is present in the published wheel (invariant 5).
- `requires_dist`: `forge-template<0.7,>=0.6`, `uv<0.13,>=0.12`, `typer>=0.16`,
  `questionary>=2.0`, `pydantic>=2.10`, `rich>=13.9`, `pyyaml>=6.0`;
  `copier<10,>=9.16` and `platformdirs>=4.3.6` only under `extra == "legacy"`.

| Field | Value |
| --- | --- |
| Commit | `261d8151871c68ccd6b33089db3b4adeaa01db3a` (working tree clean) |
| forge-template version | `0.6.0` (from `uv.lock`) |
| forge-template sdist | `forge_template-0.6.0.tar.gz` `sha256:07e036a582d038f704c5678a75d93c75cec186e8fb138b75ae08d933dd0b9db8` |
| forge-template wheel | `forge_template-0.6.0-py3-none-any.whl` `sha256:cf21152242a81b6a19d5298521a77f504063091759b5cca721b3f527c64ac742` |
| uv | `uv 0.12.16 (761ff1379 2026-09-17 x86_64-pc-windows-msvc)` |
| git | `git version 2.47.1.windows.2` |
| Python | `3.13.1` |
| Safety-relevant source digest | `sha256:2d4e809b9c70d30f45e1eb0b7b596139a7edc3ae99197f6b9c79dfbf77ca465c` (unchanged since the CF-23.01 refresh; `tests/test_update_safety_evidence.py` green) |

## Release prerequisite

The checklist in [update-safety-validation.md](update-safety-validation.md#release-prerequisite),
on the release commit:

| Item | Result |
| --- | --- |
| Digest guard green | yes; no hashed file changed in Phase A |
| `evidence:candidate` on a clean tree, wheel content digest recorded | yes; the table above |
| Both installed suites green in that commit's protected CI | yes; `End-to-end generation` 124 passed, 2 skipped (413.61 s; includes the installed Streamlit suite), `End-to-end lifecycle and update (Windows)` 5 + 32 + 9 + 14 passed (the last is the installed update-safety suite, 1 skipped for the POSIX-only symlink case) |
| `CLIENT_VERSION` matches | `0.5.0` |
| Published artefact verified | yes; the rest of this record |
| Corrected `0.4.0` guidance live, `v0.4.0` notes point at it | done for CF-22.02; not re-confirmed here |

Other checks on the release commit's run: `Windows smoke` 1470 passed, 2 skipped;
`Test (py3.13)` 1468 passed, 4 skipped; `Dependency floor`, `Network tests`,
`Wheel contents`, `Documentation` and `Lint` passed.

## Published-artefact verification

Every command below used the file or index PyPI serves, in a scratch location
(`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR` and `XDG_CONFIG_HOME` redirected so no existing
tool or configuration was touched), on Windows 11, Python 3.13.1.

### Install modes

| Mode | Result |
| --- | --- |
| `uvx --from "create-forge==0.5.0" create-forge --version` | `0.5.0` |
| `uv tool install "create-forge==0.5.0"` | installed; `--version` `0.5.0`; `list` shows **15 components** — 4 archetypes (`cli`, `data-science`, `library`, `streamlit`), 10 capabilities, 1 platform (`github`) |
| `pip install "create-forge==0.5.0"` (seeded venv) | `create-forge 0.5.0`, `forge-template 0.6.0`, **no `copier`** |
| `pip install "create-forge[legacy]==0.5.0"` | `create-forge 0.5.0`, `forge-template 0.6.0`, `copier 9.18.2`; `doctor --json` `integration.copier` `9.18.2` |

`doctor --json` (tool install) exit `0`: `integration.line` **`"v0.5.x-engine"`**,
`engine_package` `"0.6.0"`, `engine_range` `"forge-template>=0.6,<0.7"`,
ProjectSpec protocol `1`/`1`, component manifest `1,2,3`/`1,2,3`,
`metadata_version` `1`/`1`; checks `engine` (`forge-template 0.6.0 (supports
forge-template>=0.6,<0.7)`) and `engine negotiation` both `ok`.

### Generation with the published console

Each project was generated with `new --yes` and `--archetype`, then
`uv run --locked poe check` was run in it. `.forge/generation.json` was present
in every one.

| Composition | `new` | `poe check` |
| --- | --- | --- |
| `library` | exit 0 | exit 0; ruff, mypy, 1 test passed (13 s) |
| `cli` | exit 0 | exit 0; 6 tests passed (15 s) |
| `data-science --capability jupyter` | exit 0 | exit 0; 1 test passed, notebook check ran (50 s) |
| `streamlit` | exit 0 | exit 0; ruff, mypy, 3 tests passed (67 s) |
| `streamlit --capability scientific-python` | exit 0 | exit 0; mypy, 4 tests passed (96 s) |

The first `data-science` attempt omitted `--capability jupyter` and the CLI
refused with `component 'data-science' requires selected component(s): jupyter`
and `Add --capability jupyter` — the documented rule, not a defect; the recorded
run supplied the capability.

### Update and the legacy route

- **Engine-native update** on the generated `streamlit --capability
  scientific-python` project: `create-forge update --dry-run` printed
  `17 unchanged target(s).` / `Dry run complete. No project files changed.`
  (exit 0); `create-forge update` printed `Updated. Nothing changed.` (exit 0),
  `HEAD` unchanged, `git status --porcelain` empty.
- **`--legacy` Copier generation:** `new --legacy --template library` with the
  `[legacy]` install exited 0, wrote `.copier-answers.yml` (`_commit: v0.6.0`)
  and committed the project.
- **Observed, not caused by this release: `create-forge update` on that legacy
  project exits 1** with `Copier could not complete the template operation`,
  and `copier update --defaults --trust` run directly reports `Task 'git commit
  --no-verify -m "feat: initial scaffold from template"' returned non-zero exit
  status 1` after `nothing to commit, working tree clean`. The template's own
  post-generation task commits unconditionally, which fails when an update
  regenerates an identical tree. **`create-forge 0.4.0` behaves identically**
  (same steps, same exit status), so it is not a `0.5.0` regression, and the task
  belongs to `forge-template`'s Copier template. The `0.4.0` record exercised
  `new --legacy` and `poe check` but not a legacy `update`, so this is newly
  observed rather than newly introduced. Unfiled by this record.

### The `0.4.0` pin-back

`create-forge[legacy]==0.4.0` still resolves (with `forge-template 0.5.0` and
`copier 9.18.2`), `--version` prints `0.4.0`, `new --legacy` exits 0, and engine
generation of a `library` (`new --archetype library --yes`) exits 0 with
`poe check` passing (1 test).

## The installed suites against the published wheel

The suites were run **unchanged, from this repository's tests, against the wheel
downloaded from PyPI**, through `CREATE_FORGE_CANDIDATE_WHEEL` (ADR 0056
decision 5; the fixture refuses a wheel for another version).

| Suite | Result |
| --- | --- |
| `tests/test_e2e_installed_update_safety.py` | **14 passed, 1 skipped in 61.20 s**; the skip is `test_a_symlinked_parent_that_escapes_is_refused`, POSIX-only |
| `tests/test_e2e_installed_streamlit.py` | **17 passed, 0 failed, 0 skipped**, in four foreground invocations (see below) |

The Streamlit suite could not be run as one command on this host. A first
background run reached 2 of 17 tests (`composition[alone]` and
`composition[jupyter]`, both passed) and was then stopped by the development
environment for low system memory (about 380 MB free of 6 GB) during the third
test. It was not restarted on its own; when asked to complete it, it was re-run
in **foreground chunks** selected with `-k`, each under the tool's ten-minute
limit, and **every one of the 17 tests ran in one of them**:

| Chunk | Tests | Result |
| --- | --- | --- |
| Discovery, provider line and failure cases | `list_shows_streamlit_from_discovery`, `previous_provider_line_is_rejected_before_any_write`, `previous_provider_line_is_visible_in_doctor`, the four `selection_failure` cases, `non_empty_destination_is_preserved`, `lock_failure_leaves_no_partial_project` | 9 passed in 29.08 s |
| The four compositions | `composition[alone]`, `[jupyter]`, `[scientific-python]`, `[jupyter-scientific-python]` | 4 passed in 420.55 s |
| Python window edges | `full_streamlit_composition_passes_python_window_edge[3.11]`, `[3.14]` | 2 passed in 314.45 s |
| Documented recipes | `documented_recipe_runs_through_the_installed_console[plain]`, `[scientific-python]` | 2 passed in 152.54 s |

The chunks are separate pytest sessions, so each built its own isolated
environment from the same wheel; the suite's session-scoped fixtures were not
shared across them. The earlier partial run's two passes are not counted.

## Documentation

Phase B (this change) removes the `exclude_docs` entry, adds the Streamlit page to
the navigation, and updates `site_description`, `projects.md`, `capabilities.md`,
`index.md`, `installation.md` (engine range `>=0.6,<0.7`, example pins `0.5.0`),
`reference.md`, `updates.md`, `migration.md` and the root `README.md`.
`updates.md` and `migration.md` now say that `0.4.0` prints the older recovery
command and that `0.5.0` and later choose their guidance from the repository's
actual Git state (ADR 0053), which the update-safety suite above exercised on the
published wheel.

The live site is deployed by the `Publish documentation` workflow when this change
merges, so it cannot be recorded here. The deployed pages are checked after the
merge and the result is posted on #167.

Between Phase A merging (2026-09-21T21:50:13Z) and the tag being created
(22:21:25Z), `main`'s contract tables described `0.5.0` as released for about 31
minutes (ADR 0056 consequences).

**Not changed, and noticed:** `projects.md` and `capabilities.md` say there are no
platform components in the current engine catalogue, while the published wheel's
`list` shows a `github` platform. That wording predates this release and is left
for its own change.

## Roadmap reconciliation

`docs/roadmap-v4/**` is hash-pinned and stays byte-identical (ADR 0049
decision 5, ADR 0056 decision 7); this table is the reconciliation.

| Item | Delivered by |
| --- | --- |
| CF-21.01 — adopt the `forge-template 0.6` provider line | [ADR 0050](adr/0050-adopt-the-0-6-streamlit-provider-line.md), merged as `c9a33cc` |
| CF-21.02 — validate Streamlit through the installed console, document it | [ADR 0051](adr/0051-validate-installed-streamlit-generation.md), merged as `11c42f7` |
| CF-22.01 / 22.02 / 22.03 — contain, recover and evidence updates | ADRs [0052](adr/0052-contain-every-client-filesystem-target.md), [0053](adr/0053-recover-updates-from-the-actual-git-state.md), [0054](adr/0054-verify-installed-update-safety-on-the-release-candidate.md); PRs #207, #208, #210 |
| CF-23.01 — decode subprocess output by rule | [ADR 0055](adr/0055-capture-subprocess-output-as-bytes-and-decode-by-rule.md); PR #215 |
| CF-21.03 — publish and verify | [ADR 0056](adr/0056-publish-create-forge-0-5-0.md); PRs #216 (Phase A) and this change (Phase B) |

Closing #167, CF-EPIC-21 and the Stage 21 milestone is the maintainer's decision
and is not made by this record.

## Boundaries retained

Documentation and one guard test only: this change edits nothing under `src/`, no
CLI surface, dependency, protocol, lock or generated byte, and does not touch
`release.yml`. `create-forge 0.3.x` and `0.4.x` remain installable
(`0.4.0` was re-checked above). A defect found in `0.5.0` is corrected forward as
`0.5.1` with `0.5.0` yanked, never re-uploaded.
