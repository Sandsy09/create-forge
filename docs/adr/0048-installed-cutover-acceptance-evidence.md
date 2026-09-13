# 48. Complete the installed cutover acceptance evidence and the user guide's post-cutover voice

## Status

Accepted

## Context

CF-18.06 (#163) is the last test-and-docs child of CF-EPIC-18 before CF-18.07
publishes `create-forge 0.4.0`. `docs/engine-cutover-acceptance.md`'s accepted
matrix assigns it six rows (172, 219, 220, 221, 228, 229), each naming an
evidence command. Measured against the live repository, three of those six
commands select **zero tests**
(`uv run pytest tests/test_e2e_installed_cutover.py -k install_modes`,
`-k "incompatible or invalid or failure"`, and `-k boundary` each report "no
tests collected"), a fourth (`-k "credential or secret"` against
`tests/test_cli.py tests/test_runner.py`) selects one test and none from the
first file it names -- `test_cli.py`'s five `credential`/`secret` occurrences
are prose inside other tests' docstrings and bodies, not names `-k` can
match -- and the sixth's "recipe checks in
`tests/test_e2e_installed_cutover.py`" do not exist in any form.

Separately, `docs/user-guide/` -- the single published Forge user guide
(ADR 0035) -- was audited page by page. Nine of its eleven pages still
describe the pre-cutover `0.3.2` world: `--engine-preview` appears eleven
times across six files as a live command, `create-forge[engine]` twelve
times, the engine range is still quoted as `forge-template==0.4.1`, and
`docs/user-guide/projects.md`'s workflow table still lists every engine
archetype's update support as "Not supported" even though CF-18.03 gave the
engine `new` path its own Git/hook lifecycle and CF-18.04 shipped its
engine-native `update`. `tests/test_cutover_acceptance_contract.py`'s own
tripwire (`test_tripwire_user_guide_still_says_the_cutover_is_unscheduled`)
exists to force this reconciliation and names CF-18.06 in its docstring.

Two constraints shape what "complete the evidence" can mean without
duplicating work already accepted elsewhere:

- `tests/test_e2e_installed_rollout.py` (CF-14.03, ADR 0033) already proves
  most of what rows 219/220 ask for at the same installed-wheel boundary: a
  16-case selection/option/destination failure matrix, a real emptied-`PATH`
  lock failure, a real out-of-range `forge-template 0.3.2`, an engine-less
  install, and `doctor --json` reporting both. Re-deriving all of it inside
  `tests/test_e2e_installed_cutover.py` would duplicate real subprocess work
  inside the `e2e` job's existing 60-minute budget for no new evidence.
- `docs.yml` deploys the published site on every push to `main` touching
  `docs/user-guide/**`. The guide's own words say "The user guides describe
  released behaviour," but PyPI's latest release is still `0.3.2` when this
  merges -- `create-forge 0.4.0` only exists after CF-18.07 tags and
  publishes it.

## Decision

1. **Row 172 (install modes): resolve, then generate once per mode, no
   generated-project check.** Each of the four contractual install modes
   (`uvx`, `uv tool install`, `pip install`, `create-forge[legacy]`) gets its
   own isolated environment, one `doctor --json` resolution check, and one
   `new --archetype library --yes` generation asserting the tree,
   `.forge/generation.json`, and `uv.lock` exist. No test runs the generated
   project's own `uv run --locked poe check` per mode -- `test_e2e_installed_rollout.py`
   and `test_e2e_installed_cutover.py`'s own legacy tests already prove a
   generated project passes its own check at this boundary; re-running it four
   more times proves nothing new and risks the job's time budget.

2. **Rows 219/220 (failure/boundary): cover only what predates the rollout
   suite, and map the rest.** New tests in `tests/test_e2e_installed_cutover.py`
   cover exactly the cutover-specific surfaces `test_e2e_installed_rollout.py`
   cannot, because they postdate it: an engine-native `.forge/generation.json`
   project's `update` against an incompatible/missing engine, an engine-native
   update's merge-conflict recovery path, a declined `--degraded` fallback,
   and an `--engine-source` override pointed at an incompatible pin -- plus one
   thin re-assertion of the out-of-range/no-engine boundary so `-k boundary`
   and `-k incompatible` are non-empty in this file specifically. The new
   evidence record (`docs/engine-cutover-validation.md`) explicitly maps the
   pre-existing rollout-suite tests onto rows 219/220 so their coverage is
   named, not silently assumed.

3. **The OS/Python axis is discharged without a new CI job.** `e2e-windows`
   (already running `windows-latest` for the CF-18.03/18.04 lifecycle and
   update suites) gains one more step running the cutover suite's
   install-mode and legacy tests. One install-mode test parametrises over the
   Python window edges (3.11 and 3.14), mirroring
   `test_e2e_installed_data_science.py`'s `_PYTHON_WINDOW_EDGES`. The
   remaining window (3.12, 3.13) and every other module stay covered by the
   existing `test` matrix and `floor` job -- this issue does not widen the
   `e2e` job's runner or Python version.

4. **Row 229's "recipe checks" are hand-written tests plus a drift guard, not
   extracted fenced blocks.** Each documented recipe (diagnose with `doctor`,
   the preview-project regeneration guidance, a legacy update preserving
   edits, the rollback sequence, the `0.3.x` pin-back path) gets its own
   `test_recipe_*` in the installed cutover suite, running the real command
   through the installed console. A fast-suite guard separately asserts the
   command strings those tests execute are still byte-present in the
   corresponding `docs/user-guide/*.md` file, so a doc edit that silently
   changes a command the test still runs against the old string fails fast.
   Parsing runnable code fences out of Markdown was considered and rejected:
   it would need a tagging convention to separate runnable from illustrative
   blocks for a payoff of roughly six recipes -- more moving parts than the
   problem justifies.

5. **The user guide is rewritten in full, present tense, with an explicit
   version note.** All nine stale pages are corrected in this issue rather
   than a subset, because the guide is densely cross-linked and a partial
   rewrite produces direct contradictions (e.g. `updates.md` describing an
   engine-native update route while `projects.md` still says engine projects
   cannot update). Each rewritten page carries one version-note sentence
   naming that it describes `create-forge 0.4.0` and later, with a pointer to
   the `0.3.x` behaviour it replaces -- correcting the record now rather than
   waiting for CF-18.07's publication, and flipping
   `test_tripwire_user_guide_still_says_the_cutover_is_unscheduled` in this
   change rather than leaving it stranded against its own docstring. A new
   `docs/user-guide/migration.md` page, added to the mkdocs nav, carries the
   `0.3.x`→`0.4.0` migration, the preview-project regeneration recipe, the
   `git restore . && git clean -fd` rollback recipe, and the `0.3.x` pin-back
   path the 90-day support window (`docs/engine-cutover-acceptance.md`)
   promises -- consolidated in one place rather than folded into `updates.md`,
   so CF-18.07's release notes have a single page to link.

6. **Test ownership stays narrow.** This issue does not modify
   `tests/test_e2e_installed_rollout.py`, `tests/test_engine_source.py`, or
   `tests/test_update_engine.py` -- it only extends
   `tests/test_e2e_installed_cutover.py` and `tests/test_cli.py`, and records
   every other file's existing coverage in the new evidence record rather than
   re-deriving it.

## Consequences

- Closes the CF-18.06 acceptance criteria and its share of
  **CF-ROADMAP-01-AC-04** ("missing/incompatible providers, invalid
  selections and render/finalise failures have stable statuses and never
  silently fall back to Copier") and **CF-ROADMAP-01-AC-06** ("implementation,
  migration E2E, legacy regression and release tasks are filed separately
  with an explicit dependency graph").
- `tests/test_e2e_installed_cutover.py` grows from CF-18.05's four tests to
  cover install modes, the cutover-specific failure/boundary surfaces, a
  corrected `-k "credential or secret"` selector (via a `tests/test_cli.py`
  rename/addition, not a new file), and the documented recipes.
  `.github/workflows/ci.yml`'s `e2e-windows` job gains one more step; the
  `e2e` job's runner and Python version are unchanged.
- New `docs/engine-cutover-validation.md` (mirroring
  `docs/rollout-regression-validation.md`) maps every CF-18.06 acceptance
  criterion, including the rows it shares with the pre-existing rollout
  suite, to a named test. Linked from `docs/README.md` and
  `docs/end-to-end-tests.md` with a link-audit test in
  `tests/test_engine_contract.py`.
- `docs/user-guide/index.md`, `installation.md`, `cli.md`, `updates.md`,
  `reference.md`, `projects.md`, `library.md`, `cli-application.md`,
  `data-science.md`, and `capabilities.md` are rewritten for the shipped
  cutover; a new `docs/user-guide/migration.md` is added to `mkdocs.yml`'s
  nav. `docs/cli-conventions.md`'s "Still open" line for CF-18.06 is cleared;
  `docs/engine-cutover-acceptance.md`'s Status section and matrix preamble are
  corrected to state the cutover has not yet published but the suite this
  issue adds to already existed before CF-18.06 (CF-18.05 created it).
- `tests/test_cutover_acceptance_contract.py`'s
  `test_tripwire_user_guide_still_says_the_cutover_is_unscheduled` and
  `test_tripwire_installed_cutover_suite_does_not_yet_cover_the_full_matrix`
  flip to derived assertions (narrowed or removed per their own docstrings).
  `test_tripwire_version_is_not_yet_the_cutover_release` (CF-18.07's) is
  untouched.
- No `forge-template` change (CF-ROADMAP-01-EX-01): this ADR is entirely
  client-side test coverage, CI wiring, and documentation.
