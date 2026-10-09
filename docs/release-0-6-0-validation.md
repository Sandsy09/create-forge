# create-forge 0.6.0 release validation

Records the published `create-forge 0.6.0` / `forge-template 0.7.0` pair
verified against its own artefacts, and the close-out of the batch client work
(CF-29.03, [#206](https://github.com/Sandsy09/create-forge/issues/206),
[ADR 0064](adr/0064-publish-create-forge-0-6-0.md)). It follows
[release-0-5-0-validation.md](release-0-5-0-validation.md)'s shape. Everything
below was measured on 2026-10-09 against what PyPI serves, not against the
working tree, except where a row says otherwise. The output is verbatim where it
is quoted and summarised where it says so.

Nothing here claims an engine cutover: `0.6.0` is a compatibility-line crossing
to the `forge-template 0.7` provider line (a sixteenth component, the `batch`
archetype), with no protocol, `metadata_version` or facade change.

## Release identity

| Fact | Value |
| --- | --- |
| Release commit | `80eaa3650716ba4937f025ab89d767c114c2d725` (PR [#252](https://github.com/Sandsy09/create-forge/pull/252), squash of Phase A, merged 2026-10-09T19:28:33Z) |
| Tag | `v0.6.0`, annotated (`61b424a4…`), created 2026-10-09T19:41:33Z, **dereferences to the release commit** |
| Protected CI on the release commit | [run 37980475548](https://github.com/Sandsy09/create-forge/actions/runs/37980475548), all 17 jobs passed (including `All checks passed` and `Dependency audit`); the runner canary and the documentation publish also succeeded |
| Dry run | [run 37981695593](https://github.com/Sandsy09/create-forge/actions/runs/37981695593), `headSha` equal to the release commit; `Create tag` and `GitHub release` skipped, `Publish to PyPI` skipped; created no tag, release or upload |
| Real release | [run 37981893113](https://github.com/Sandsy09/create-forge/actions/runs/37981893113), `headSha` equal to the release commit; `Dependency audit`, `release` and `Publish to PyPI` all succeeded |
| GitHub release | [v0.6.0](https://github.com/Sandsy09/create-forge/releases/tag/v0.6.0), not a draft, not a pre-release, published 2026-10-09T19:41:35Z |
| PyPI | `create-forge 0.6.0`, latest; wheel uploaded 19:42:14Z, sdist 19:42:16Z |
| Dispatch authority | The real dispatch was made only after the maintainer's explicit go, after the dry run and after re-checking that `main` had not moved and that `v0.6.0` did not exist (ADR 0064 decision 4) |

The dry run printed no commit; its run's `headSha` was read and compared with the
commit whose CI had passed, and `origin/main` was re-read immediately before the
real dispatch.

## Published artefacts

| File | Size | Archive sha256 (PyPI) | Content digest |
| --- | --- | --- | --- |
| `create_forge-0.6.0-py3-none-any.whl` | 109458 | `b48e99a71b3bf5258e150410562801754216f0b7661e825888f13c2d61a19455` | `sha256:d3210780b2c27b8ce8de43807ec01fdd9506d60289b2f52c358045d9368f29a3` |
| `create_forge-0.6.0.tar.gz` | 356537 | `b560d65f8b25b8f366618bbc531205adde1c784754b8c5a0836b5a96e6e0a836` | `sha256:a97eb61f8654061bc49c73cd0e23d6bb0d1c8205d609258f49026716934baad5` |

Bound to the candidate by `uv run poe evidence:candidate` on the clean release
commit (run before the release) and `scripts/candidate_evidence.py --archive` on
the downloaded files (ADR 0054's content-digest rule). Both downloads' sha256
equalled what PyPI reports.

- The **wheel content digest is identical** to the candidate's, so the published
  wheel is byte-for-byte the same members the protected CI validated.
- The **wheel archive sha256 differs** (the candidate build on the maintainer's
  Windows host `dafaecad242e57cbcf8c90d3bbe74de32258f8bb6d1d78dd52a80c3d528ded8d`
  against PyPI's `b48e99a7…`). This is the build-environment effect ADR 0054
  documents (identical members, different compressed stream), not a difference in
  what shipped.
- The **sdist archive sha256 and content digest both match** the local build.
- `create_forge/templates.toml` is present in the published wheel (invariant 5),
  alongside the whole `commands/` package.
- `requires_dist`: `forge-template<0.8,>=0.7`, `uv<0.13,>=0.12.18` (ADR 0063),
  `typer>=0.16`, `questionary>=2.0`, `pydantic>=2.10`, `rich>=13.9`,
  `pyyaml>=6.0`; `copier<10,>=9.16` and `platformdirs>=4.3.6` only under
  `extra == "legacy"`.
- The locked `forge-template 0.7.0` hashes in the candidate evidence (sdist
  `7d0e2364…`, wheel `edaf0604…`) equal the provider's published receipt.

## Release prerequisite

The checklist in [update-safety-validation.md](update-safety-validation.md#release-prerequisite),
on the release commit:

| Item | Result |
| --- | --- |
| Digest guard green | yes; no hashed file changed in Phase A (safety-relevant source digest `sha256:719ee6b36faff3ff4bd9500580690b4b6abbccb86f58ced88648808e2383ddb6`) |
| `evidence:candidate` on a clean tree, wheel content digest recorded | yes; the table above |
| Both installed suites green in that commit's protected CI | yes; `End-to-end generation` 187 passed, 12 skipped (515.06 s; includes the installed batch, Streamlit and update-safety suites), `End-to-end lifecycle and update (Windows)` 5 + 36 + 15 + 18 + 11 passed (the 18 is the installed update-safety suite, 1 skipped for the POSIX-only symlink case; the 11 is the new "Installed batch tests" step) |
| `CLIENT_VERSION` matches | `0.6.0` |
| Published artefact verified | yes; the rest of this record |
| Corrected `0.4.0` guidance live, `v0.4.0` notes point at it | done for CF-22.02; not re-confirmed here |

Other checks on the release commit's run: `Windows smoke` 1625 passed, 2 skipped;
`Test (py3.13)` 1623 passed, 4 skipped; `Dependency floor`, `Network tests`,
`Wheel contents`, `Documentation` and `Lint` passed. `Installed console encoding`
passed on Windows Python 3.11, 3.13 and 3.14.

## Published-artefact verification

Every command below used the file or index PyPI serves, in a scratch location
(`UV_TOOL_DIR`, `UV_TOOL_BIN_DIR` and `XDG_CONFIG_HOME` redirected so no existing
tool or configuration was touched), on Windows 11, Python 3.13.1.

### Install modes

| Mode | Result |
| --- | --- |
| `uvx create-forge@0.6.0 --version` | `0.6.0`; `uvx create-forge@0.6.0 list` shows **16 components** — 5 archetypes (`batch`, `cli`, `data-science`, `library`, `streamlit`), 10 capabilities, 1 platform (`github`) |
| `uv tool install "create-forge==0.6.0"` | installed; `--version` `0.6.0`; `new --archetype batch` generated a project with a lock |
| `pip install "create-forge==0.6.0"` (venv) | `create-forge 0.6.0`, **no `copier`** |
| `pip install "create-forge[legacy]==0.6.0"` | `create-forge 0.6.0`, `copier 9.18.2` |

`doctor --json` (via `uvx`) exit `0`: `integration.line` **`"v0.6.x-engine"`**,
`engine_package` `"0.7.0"`, `engine_range` `"forge-template>=0.7,<0.8"`,
ProjectSpec protocol `1`/`1`, component manifest `1,2,3`/`1,2,3`,
`metadata_version` `1`/`1`; checks `engine` and `engine negotiation` both `ok`.

### Generation with the published console

Each project was generated with `uvx create-forge@0.6.0 new --yes --archetype …`,
then `uv run --locked poe check` was run in it.

| Composition | `new` | `poe check` |
| --- | --- | --- |
| `library` | exit 0 | exit 0; 1 test passed |
| `cli` | exit 0 | exit 0; 6 tests passed |
| `data-science --capability jupyter` | exit 0 | exit 0 |
| `streamlit` | exit 0 | exit 0; 3 tests passed |
| `batch` | exit 0 | exit 0; 3 tests passed |

For `batch`, `uv run poe run` also exited 0 (`INFO: processed 3 record(s)`) and
wrote `data/output.json` (154 bytes).

### Update and the legacy route

- **Engine-native update** on the generated `library` project: `create-forge
  update --dry-run` printed `Dry run complete. No project files changed.` (exit 0);
  `create-forge update` printed `Updated. Nothing changed.` (exit 0) and left
  `git status --porcelain` empty.
- **`--legacy` Copier generation:** `new --legacy` with the `[legacy]` install
  exited 0, wrote `.copier-answers.yml` (`_commit: v0.7.0`) and committed the
  project.
- **A real legacy `update` now succeeds.** `create-forge update` on that legacy
  project exited 0 (`Updated. Review the diff before committing — conflicts are
  marked inline.`) with a clean tree; `update --dry-run` also exited 0. The
  [`0.5.0` record](release-0-5-0-validation.md#update-and-the-legacy-route)
  observed the same command exiting 1, because the template's own post-generation
  task committed unconditionally and failed on an identical tree. `forge-template
  0.7.0` made those tasks copy-only, which this run confirms end to end on the
  published client.

### The `0.5.0` pin-back

`uvx create-forge@0.5.0` still works on its own provider line: `--version` prints
`0.5.0`, `doctor --json` reports `engine_package` `"0.6.0"`, `engine_range`
`"forge-template>=0.6,<0.7"` and `integration.line` `"v0.5.x-engine"`, and `new
--archetype library --yes` exits 0 with a lock and `provider.version` `0.6.0` in
`.forge/generation.json`. The published `0.5.0` does not know `batch`
(`tests/test_e2e_installed_cross_line.py` asserts it is an unknown archetype to
that client).

## The installed suites against the published wheel

The suites were run **unchanged, from this repository's tests, against the wheel
downloaded from PyPI** (sha256 `b48e99a7…`), through
`CREATE_FORGE_CANDIDATE_WHEEL` (ADR 0056 decision 5; the fixture refuses a missing
file, a non-wheel or a wheel for another version, and returns the supplied wheel
before any build).

| Suite | Result |
| --- | --- |
| `tests/test_e2e_installed_update_safety.py` | **18 passed, 1 skipped in 65.31 s**; the skip is `test_a_symlinked_parent_that_escapes_is_refused`, POSIX-only |
| `tests/test_e2e_installed_batch.py` | **18 passed in 466.90 s (7:47)**: the four compositions, the 3.11 and 3.14 edges, the failure matrix, both recipes |
| `tests/test_e2e_installed_streamlit.py` | **17 passed in 697.76 s (11:37)**: the four compositions, the 3.11 and 3.14 edges, the failure cases, both recipes |
| `tests/test_e2e_installed_cross_line.py` | **6 passed in 40.42 s**: with the published `0.6.0` as the "candidate", the published `create-forge 0.5.0` (on its own `0.6` engine) and the published `0.6.0` (on `0.7.0`) generate byte-identical `library`, `cli`, `data-science` and `streamlit` projects apart from `uv.lock` and the provider version recorded in `.forge/generation.json`; the two controls hold |

The suites were run one module at a time, each as its own background command with
a log, because the development host has about 6 GB of memory and has stopped long
runs before.

## Documentation

Phase B (this change) removes the `exclude_docs` entry, adds the Batch page to the
navigation, and updates `site_description`, `projects.md`, `index.md`,
`installation.md` (engine range `>=0.7,<0.8`, example pins `0.6.0`), `cli.md`,
`reference.md` and the root `README.md`. `updates.md` and `migration.md` are
unchanged: they say "`0.5.0` and later", which still holds.

The live site is deployed by the `Publish documentation` workflow when this change
merges, so it cannot be recorded here. The deployed pages are checked after the
merge and the result is posted on #206.

The generated release notes cannot mention `batch`: the adoption was a `chore:`
commit and `git-cliff` omits `chore:`. As for `0.5.0`, a hand-written **Highlights**
section is prepended to the GitHub release body (ADR 0064 decision 7), after the
guide it links to is live. `CHANGELOG.md` itself is left exactly as generated.

Between Phase A merging (2026-10-09T19:28:33Z) and the tag being created
(19:41:33Z), `main`'s contract tables described `0.6.0` as released for about 13
minutes (ADR 0064 consequences).

## Observed during the release

- **A hard-coded `uv` specifier in an e2e test slipped past `poe check`.** Raising
  the `uv` floor (ADR 0063, [#251](https://github.com/Sandsy09/create-forge/pull/251))
  broke `test_candidate_wheel_installs_the_reviewed_pair`, which spells the range
  as `{">=0.12", "<0.13"}`; a search for the string `uv>=0.12` could not find it
  and the fast suite deselects e2e. The protected CI e2e job caught it before
  merge. Phase A therefore ran the version-sensitive e2e modules locally before
  pushing.
- **Two Dependabot branches were stale, not broken.** #243 and #244 were cut before
  the `0.7` adoption and the audit lock refresh, so their CI ran a `0.6`-pinned
  client against a repo whose "latest template" is `v0.7.0`. Rebased onto current
  `main` they were fully green.
- **The `git-cliff` upgrade (2.13 to 2.14) reorders group headings** in every
  historical changelog section; all 87 earlier entries are still present and none
  is duplicated.
- **Unchanged and still open:** the `pypi` environment has no protection rules;
  three install hints still say `uv>=0.12,<0.13` (ADR 0063 decision 4); the CI
  `UV_VERSION` scanner pin is `0.12.0`.

## Roadmap reconciliation

`docs/roadmap-v5/**` is mirrored byte for byte from `forge-template` and stays
identical (ADR 0064 decision 8); this table is the reconciliation.

| Item | Delivered by |
| --- | --- |
| CF-29.01 — adopt the `forge-template 0.7` provider line | [ADR 0061](adr/0061-adopt-the-0-7-batch-provider-line.md), merged as `1416ec8` (PR #248); the audit lock refresh that unblocked it, PR #247 |
| CF-29.02 — validate batch through the installed console, document it | [ADR 0062](adr/0062-validate-batch-through-the-installed-candidate.md), merged as `6f15a9f` and `f16dbd7` (PRs #249, #250) |
| `uv` floor raised past a published advisory | [ADR 0063](adr/0063-raise-the-uv-floor-to-0-12-18.md), merged as `589c9b3` (PR #251) |
| Dependabot bumps merged before the freeze | PRs #246 (platformdirs), #244 (ruff), #243 (mypy) |
| CF-29.03 — publish and verify | [ADR 0064](adr/0064-publish-create-forge-0-6-0.md); PRs #252 (Phase A) and this change (Phase B) |

#206 and CF-EPIC-29 ([#192](https://github.com/Sandsy09/create-forge/issues/192))
are closed with these receipts once this change has merged and the deployed pages
are checked; the Stage 29 milestone is left to the maintainer.

## Boundaries retained

This is documentation, evidence and a release. It changes nothing under `src/`
beyond what Phase A recorded (`INTEGRATION_LINE`), no CLI surface, dependency,
protocol, lock or generated byte, and it does not touch `release.yml`. It does not
change the `pypi` environment's missing protection rules.

When this release evidence changes, update this record and the
[docs index](README.md) in the same pull request.
