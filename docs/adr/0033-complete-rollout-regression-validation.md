# 33. Complete the rollout regression and failure matrix at the installed boundary

## Status

Accepted

## Context

[Issue #113 / CF-14.03](https://github.com/Sandsy09/create-forge/issues/113)
is the third child of
[CF-EPIC-14](https://github.com/Sandsy09/create-forge/issues/104). CF-14.01
prepared create-forge `0.3.0` and adopted `forge-template>=0.4.1,<0.5`
([ADR 0031](0031-adopt-the-reviewed-forge-template-0-4-1-release.md)); CF-14.02
built that candidate wheel, installed it with the published engine, and
validated the two accepted Data Science compositions through the resulting
console script
([ADR 0032](0032-validate-installed-data-science-generation.md)). Both of
those records name what they left for this issue:
`docs/installed-data-science-validation.md` — *"CF-14.03 owns the installed
Library/CLI, default Copier, compatibility, selection, filesystem-failure, and
cleanup regression matrix"* — and ADR 0032 decision consequence 2 repeats it.

The gap was measured, not assumed. Library, CLI Application, and the default
Copier path were proven only from the *editable* development console —
`tests/test_e2e_engine_generation.py` and `tests/test_e2e_generation.py`
resolve `shutil.which("create-forge")` out of this repository's own
`uv sync` environment. No test generated through the built wheel. No test
proved the Copier path works from a wheel installed with **no engine at all**
— the shape a plain `pip install create-forge` produces, and the exact silent
failure mode CLAUDE.md invariant 5 exists for. Every selection, option,
compatibility, destination, and lock failure was proven only in-process,
through Typer's `CliRunner` with a monkeypatched `EngineInfo` or a faked
`create_uv_lock`; the two real-install negatives in the engine e2e suite build
their environment with `uv run --isolated --with <repo-root>`, the source
tree, not the release candidate.

The installed catalogue was re-checked. `data-science.requires jupyter>=1,<2`
is the only relation in the five-component catalogue; nothing declares a
`conflicts` entry, so "conflicting selections" at this boundary means the
client-owned `--capability`/`--no-capabilities` contradiction and wrong-kind
ids, not an engine verdict. `forge-template 0.3.2` is a real published PyPI
release genuinely below `compat.SUPPORTED_ENGINE_RANGE`, and — because ADR
0012 only ever raises that bound — it stays below it permanently.
`staging.create_uv_lock` shells out to a bare `uv`, so an emptied `PATH` is a
real lock failure *after* a successful render, exercising `staged()`'s cleanup
for real rather than through a fake.

## Decision

1. **Re-run the regression matrix at the installed boundary, not just
   editable.** `tests/test_e2e_installed_rollout.py` builds the same
   `create_forge-0.3.0` wheel CF-14.02 introduced and drives its console
   script for Library and CLI Application: project shape, current lock,
   Foundation/component ownership of every rendered byte, no Forge
   distribution in any dependency table or the lock, the `cli` console-script
   name, and `uv run --locked poe check`. This is the counterpart to the
   editable `tests/test_e2e_engine_generation.py`, one release layer out.

2. **Run the default Copier path in the engine-less environment.** A second
   installed environment gets the wheel with no `engine` extra. One real
   Copier generation there — clone, `_tasks`, `.copier-answers.yml`
   round-trip, `.git` and `uv.lock`, `uv run poe check` — simultaneously
   proves the default path works from a wheel *and* that it needs nothing
   from `forge-template`. The no-engine command surface (`--version`, `list`,
   `doctor --json`, and `new --engine-preview`'s actionable rejection) is
   checked in the same environment.

3. **Use a real out-of-range engine for the compatibility boundary.** A third
   environment resolves `forge-template==0.3.2` from PyPI alongside the
   candidate wheel. `new --engine-preview` there exits `3` naming both the
   installed `0.3.2` and the supported range, with nothing written;
   `doctor --json` reports `engine_package: "0.3.2"` against the unchanged
   range. This mirrors the editable suite's two-isolated-install approach
   ([ADR 0020](0020-engine-path-end-to-end-tests.md)) rather than a
   monkeypatched `EngineInfo`.

4. **Run the whole failure matrix through the installed console,
   parametrised.** Unknown and wrong-kind archetypes and capabilities,
   contradictory and misplaced flags, a missing hard requirement in both the
   absent and explicit-empty forms, unknown / unselected / undeclared
   component options, an engine-preview Copier flag, malformed `--data` and
   `--component-option`, and a non-empty destination on both paths — each
   asserting the documented exit status
   (`docs/cli-conventions.md`'s table), an actionable message fragment, the
   destination absent or byte-identical to before, and no surviving
   `.create-forge-*` staging sibling. A single parametrised test, cheap
   because none of these cases renders or locks.

5. **Prove the atomic lock failure without a fake.** One test generates
   `library` with `PATH` set to a single empty directory: the engine render
   succeeds, `staging.create_uv_lock` cannot launch `uv`, and the run exits
   `1` with the documented message, no destination, and no staging sibling —
   the one case here that exercises `staged()`'s real cleanup path.

6. **Extract the installed-client harness rather than duplicate it.**
   CF-14.02's wheel build, virtual-environment construction, subprocess
   plumbing, and the installed-pipeline ownership probe move to
   `tests/installed_client.py`; `tests/conftest.py` gains session-scoped
   `candidate_wheel` and `installed_client` fixtures both suites share, so the
   wheel is built once and the `[engine]` environment once per session. The
   ownership probe is generalised to read its archetype from the JSON payload.
   `tests/test_e2e_installed_data_science.py` keeps every assertion it had.

7. **Record this as its own ADR and canonical doc.** CF-14.02
   ([ADR 0032](0032-validate-installed-data-science-generation.md)) and
   CF-13.05 ([ADR 0030](0030-data-science-preview-pipeline-validation.md))
   each did. `docs/rollout-regression-validation.md` maps #113's five
   acceptance criteria, and the epic criteria it discharges, to the named
   tests; it is linked from `CLAUDE.md` and `CONTRIBUTING.md` with a
   link-audit case in `tests/test_engine_contract.py`.

## Consequences

- No shipped module changes. `tests/installed_client.py` and
  `tests/test_e2e_installed_rollout.py` are new; `tests/conftest.py` gains two
  session fixtures; `tests/test_e2e_installed_data_science.py` imports the
  shared harness instead of defining it.
- `.github/workflows/ci.yml`'s `e2e` job `timeout-minutes` rises 45 → 60 for
  the two extra virtual environments, the two engine-path projects with their
  own checks, and the engine-less Copier generation with `_tasks`. No new
  job; `all-green`'s `needs` list is unchanged.
- `docs/rollout-regression-validation.md` is new.
  `docs/end-to-end-tests.md`, `docs/installed-data-science-validation.md`,
  `docs/filesystem-generation.md`, `docs/cli-conventions.md`, and
  `docs/engine-resolution.md` retire their forward references to CF-14.03 and
  link this record; `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, and the
  Stage 14 roadmap records follow.
- This closes CF-14.03. It is **not** the CLI cutover, and it publishes
  nothing: `--engine-preview` stays hidden and dev-only, the default `new`
  path stays direct-Copier, and the create-forge `0.3.0` changelog, tag, and
  PyPI publication remain CF-14.04's.
