# CLI decomposition validation

This is the closing evidence record for
[CF-EPIC-25](https://github.com/Sandsy09/create-forge/issues/191) — CLI
Orchestration Decomposition — binding its three children's acceptance
criteria to named tests, check jobs, and a real CI run. It executes
[ADR 0060](adr/0060-cli-command-module-seams.md)'s decision; no new
architecture boundary, dependency policy, or compatibility contract was
introduced, so no new ADR accompanies it.

- [CF-25.01 (#201)](https://github.com/Sandsy09/create-forge/issues/201) —
  characterised `cli.py` and agreed the extraction seams. Delivered ADR 0060
  and [`docs/cli-command-map.md`](cli-command-map.md); no code moved.
- [CF-25.02 (#202)](https://github.com/Sandsy09/create-forge/issues/202) —
  extracted command orchestration into `src/create_forge/commands/*.py`
  behind a thin Typer layer (six PR-slices, #229/#230/#231/#237/#238/#239,
  plus a same-day documentation-consistency fixup, #240).
- [CF-25.03 (#203)](https://github.com/Sandsy09/create-forge/issues/203) —
  reorganised the tests to mirror that layout and proved the new package
  installs and runs (two PR-slices, #241 and this one).

## What this proves, and what it does not

**Proves:**

- `cli.py` shrank from 2,149 lines (CF-25.01's baseline) to a thin,
  102-statement Typer-registration layer; every command's real
  orchestration lives in one `commands/*.py` module per command, with the
  dependency direction ADR 0060 decision 3 requires (`commands/*` never
  imports `cli.py`) and the lazy-import rule ADR 0014/0060 requires
  (`copier`/`runner`/`pipeline`/`engine`/`engine_source`/`update` imported
  only inside a function body) — both machine-checked by
  `tests/test_command_layout.py`, not just documented.
- No public CLI behaviour changed anywhere in the move: every option,
  default, output string, and exit code CF-25.01's baseline recorded is
  reproduced exactly, proven by the unmodified fast-suite test bodies
  passing unchanged after both the production move (CF-25.02) and the test
  move (CF-25.03).
- The built wheel carries every shipped module, not just `templates.toml`
  (`scripts/check_wheel.py`, extended this issue).
- A plain `pip install create-forge` (no `legacy` extra) imports `cli.py`
  and every `create_forge.commands.*` submodule with `copier` absent from
  `sys.modules` and not importable at all — proven against a real installed
  wheel, not just the source (`tests/test_e2e_installed_layout.py`).
- The legacy extra, and an isolated `--engine-source` override pinned to a
  real, reviewed `forge-template` release, both work against the new
  package layout through a real installed console — including the first
  `--engine-source` run this repository's CI has ever actually executed to
  a *successful* finish (every prior installed `--engine-source` case was
  failure-path only; the one prior success case needs a sibling checkout
  and is always skipped in CI).

**Does not prove:**

- a new release. No release is claimed by this record — see
  [CONTRIBUTING.md](../CONTRIBUTING.md)'s release process; the next tagged
  release's own validation record covers the published artefact.
- a public API or CLI surface change. There is none; this is a pure
  internal refactor of both production code and its tests.

## Acceptance criteria and their evidence

| Criterion (from #201/#202/#203) | Evidence |
| --- | --- |
| Characterise `cli.py`'s current behaviour and agree extraction seams (CF-25.01) | ADR 0060; [`cli-command-map.md`](cli-command-map.md) |
| Extract command orchestration behind a thin Typer layer, no behaviour change (CF-25.02) | PRs #229–#240; `cli.py` at 102 statements; the full fast suite (1591 tests at CF-25.02's close) unchanged except for necessary test-patch re-pointing |
| Keep existing regression coverage and shared fixtures discoverable; no duplicate tests (CF-25.03-AC-01) | `tests/commands/` mirrors `src/create_forge/commands/`; a collected-node-id diff proved zero tests lost, dropped, or duplicated by the move (PR #241) |
| Built wheel, plain installation, legacy extra and isolated engine-source commands work with the new package layout (CF-25.03-AC-02) | `scripts/check_wheel.py` (module membership); `tests/test_e2e_installed_layout.py` (16 tests: plain-install import/`sys.modules` proof, every command's `--help`, `--version`, `list`, `list --legacy`, `new --legacy` naming the remedy, `doctor --json`, `config init`/`show`, and a real successful `--engine-source` run) |
| Required fast, Windows, network and end-to-end checks pass against the refactored candidate (CF-25.03-AC-03) | This PR's own CI run, `All checks passed`, named below |
| Document the module map, stable public entry points and evidence; no release claimed (CF-25.03-AC-04) | [`cli-command-map.md`](cli-command-map.md)'s "Test map"; `CLAUDE.md`/`CONTRIBUTING.md` pointers; this record; no release dispatched |

## Candidate

| | |
| --- | --- |
| Repository commit (CF-25.03 slice 1, test reorganisation) | `7e4dfc2` |
| Repository commit (CF-25.03 slice 2, this record) | filled in after merge |
| `forge-template` (engine) | `0.6.0`, pinned by `pyproject.toml`'s `forge-template>=0.6,<0.7` |
| `copier` (legacy extra) | `>=9.16,<10` |

## The installed suite against this candidate

`uv run pytest -m e2e tests/test_e2e_installed_layout.py` — 16 passed,
against a wheel built from this candidate, session-scoped across the file
so only one venv/wheel build pays for the whole suite.

## Recorded validation

To be filled in after a real CI run on the PR that lands this record, per
CONTRIBUTING's rule against a success claim based solely on local-green
tests:

| Command | Result |
| --- | --- |
| `uv run poe check` | |
| `uv run poe check:wheel` | |
| `uv run pytest tests/test_e2e_installed_layout.py -q` (local, above) | 16 passed |
| CI run (`All checks passed`) | |

## Boundaries retained

- No public API, CLI surface, dependency range, or compatibility contract
  changed. ADR 0060 is executed, not amended or superseded.
- `unsafe=True` (invariant 3), the one-Copier-API-seam / two-engine-API-seam
  rule (invariant 4), and the bundled-registry-over-remote decision (ADR
  0006) are all unaffected — this issue moved code and tests, not trust
  boundaries.
- CF-EPIC-25 closes with this record; no further child issue is planned
  under it. A future CLI change follows the ordinary
  [change process](../CLAUDE.md#change-process), landing in whichever
  `commands/*` module (and its mirror test file) it touches.
