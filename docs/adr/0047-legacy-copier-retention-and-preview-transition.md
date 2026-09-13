# 47. Reject a pre-cutover `--engine-preview` project with one diagnostic, add no migration helper, and keep the Copier route reachable without a usable engine

## Status

Accepted

## Context

ADR 0041 (CF-16.02) decided the `update` routing table as rules 7-8 of
`docs/engine-project-lifecycle.md`. Rule 7 -- route by file, `--legacy` forces
Copier -- shipped as `create_forge.update.route_for` (CF-18.04, ADR 0046).
Rule 8 fixed the *policy* for a pre-cutover `--engine-preview` project (reject
with guidance, fabricate nothing) but explicitly left CF-18.05 "the exact
wording and any migration helper it decides to add".

Two facts fix the shape of what is left to decide:

- **A `--engine-preview` project is undetectable.** `git show
  v0.3.2:src/create_forge/pipeline.py` and `engine.py` confirm the pre-cutover
  preview path wrote no `.copier-answers.yml`, no `.forge/` directory, and no
  marker of any kind. `route_for` already has only two file checks
  (`update.py`); there is no third fact to check for. A "pre-cutover preview
  project" and "any directory create-forge never touched" are the same
  on-disk shape.
- **No released preview project has an update path to lose.** The `0.3.x`
  `--engine-preview` flag was hidden, undocumented, and never the default
  (`docs/engine-updates.md` "Existing generated projects"); it never wrote an
  engine answers file, so there is nothing today's cutover could be dropping
  support for. `docs/engine-cutover-acceptance.md` confirms
  `--engine-preview` is removed with no deprecation window (decision 34,
  ADR 0040) because it carried no compatibility promise.

Separately, CF-18.05's own acceptance criteria ask to retain the direct-Copier
route's safeguards. Auditing `update_project` (`cli.py`) against that ask
found a live defect: it resolves `engine.generation_metadata_target()` before
routing, and that function's own docstring (`engine.py`) states an
out-of-range engine "may predate this constant entirely" -- so a
`.copier-answers.yml`-only project cannot be updated at all when the installed
engine is unusable, contradicting `docs/engine-cutover-acceptance.md`'s "the
direct-Copier route is not deprecated and starts no clock" and CLAUDE.md
invariant 5's engine/Copier seam separation.

## Decision

1. **One diagnostic covers every "neither file" cause.** `update.route_for`'s
   exit-`1` message, on finding neither `.forge/generation.json` nor
   `.copier-answers.yml`, now names three possible causes in one sentence --
   never created by create-forge, the provenance file was deleted, or the
   project was created by the removed development-only `--engine-preview`
   flag, which wrote neither file and never supported updates -- and points at
   regeneration with `create-forge new`. No new check, no new code path: the
   two existing `is_file()` tests are unchanged: only the message grows.

2. **No migration or adoption helper.** Considered and rejected: an
   `update --adopt` that writes `.forge/generation.json` over an existing tree
   without rendering. Rejected because (a) the project is undetectable, so
   there is no reliable trigger for it; (b) recording a spec for a tree that
   was never rendered from one means inventing answers, which the issue's own
   acceptance criteria forbid; and (c) a fabricated metadata document's
   `output` digests would not match the tree, and lifecycle rule 13
   (`removed` deleted only if pristine) and rule 22 (`--degraded` pristine-ness
   from recorded digests) both trust those digests -- a fabricated record
   would silently corrupt the first real update it powers. The safe migration
   path stays what rule 8 already named: regenerate with `create-forge new`
   and port changes by hand. This closes ADR 0041 decision 2's open clause
   with "no helper", not a deferral.

3. **The direct-Copier route stays reachable independent of engine health.**
   `update_project` now resolves the engine-native metadata filename only
   after confirming the project could route there; when the engine cannot be
   imported or is out of range, a `.copier-answers.yml` project still reaches
   `runner.update` unchanged, including its mandatory `_src_path`
   re-validation (ADR 0036). This is a bugfix to rule 7's own "the
   direct-Copier route, unchanged" promise, not a new rule -- the engine
   dependency must never gate a project that does not use the engine.

4. **`_ensure_legacy_available` names its caller.** Its exit-`3` message
   still always names `pip install 'create-forge[legacy]'`, but distinguishes
   "to use --legacy" (the `new`/forced-Copier caller) from "to update this
   project, which records Copier answers in `.copier-answers.yml`" (the
   file-routed `update` caller reached with no `--legacy` flag at all).

5. **`tests/test_e2e_installed_cutover.py` is created by this issue.**
   `docs/engine-cutover-acceptance.md`'s accepted matrix names this file as
   CF-18.05's own evidence (`-k legacy`); `tests/test_cutover_acceptance_contract.py`'s
   tripwire assumed CF-18.06 would create it first. The matrix is the accepted
   contract; the tripwire is narrowed to what CF-18.06 still owns -- the full
   override/data-science installed matrix -- rather than the file's mere
   existence.

## Consequences

- Closes **CF-ROADMAP-01-AC-05** in full ("existing Copier projects have a
  documented update/support route and the rollback plan does not corrupt
  their stored answers") -- ADR 0041 and CF-16.02 fixed the routing rule and
  the write-order guarantee; this ADR fixes the wording and the bugfix that
  keeps the route reachable regardless of engine health.
- `create_forge.update.route_for`'s message changes; both filenames stay
  present verbatim, so `tests/test_update_routing.py`'s existing assertions on
  file-name substrings are unaffected.
- `create_forge.cli.update_project` gains a narrow `except (ImportError,
  engine.EngineCompatibilityError)` fallback around metadata-filename
  resolution, routing to `_run_copier_update` when `.copier-answers.yml`
  exists; otherwise it exits `3` as an unusable-engine failure exactly as
  today. `_ensure_legacy_available` gains a caller-supplied purpose string.
- `docs/engine-project-lifecycle.md` rule 8 moves out of "decided" voice;
  `docs/cli-conventions.md`'s "Still open" line for CF-18.05 is cleared;
  `docs/engine-default-cli.md`'s CF-18.05 deferral moves into shipped voice.
- `tests/test_update_routing.py` gains `-k preview`-selectable tests;
  `tests/test_cli.py` gains `-k legacy`-selectable tests for
  `--template-url` validation, dry-run, `--ref`, and the engine-unusable
  fallback; `tests/test_e2e_installed_cutover.py` is added with the legacy and
  preview-transition scenarios the matrix assigns to CF-18.05.
  `tests/test_cutover_acceptance_contract.py`'s installed-suite tripwire
  narrows accordingly.
- `docs/user-guide/updates.md`'s migration recipe and
  `docs/user-guide/reference.md` are deliberately left to CF-18.06, whose
  acceptance criteria already own "migration, legacy support, rollback and
  user-guide recipes". This ADR's existing "Preview projects" prose stays
  accurate under the new wording without further change.
- No `forge-template` change (CF-ROADMAP-01-EX-01): this ADR is entirely
  client-side wording, routing-order, and test coverage.
