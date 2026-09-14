# 49. Publish create-forge 0.4.0 and close the Engine-Default Cutover roadmap

## Status

Accepted

## Context

[Issue #164 / CF-18.07](https://github.com/Sandsy09/create-forge/issues/164)
is the seventh and last child of
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153), and the
last open issue in the Engine-Default Cutover roadmap
([`docs/roadmap-v3`](../roadmap-v3/README.md)). Everything it depends on has
landed: CF-18.01 made the engine the default `new` path and moved `copier`
to the optional `legacy` extra ([ADR 0040](0040-engine-default-selection-and-source-resolution.md));
CF-18.02 added the isolated `--engine-source` override
([ADR 0044](0044-out-of-process-engine-source-overrides.md)); CF-18.03 shipped
the engine `new` Git/hook lifecycle and `.forge/generation.json`
([ADR 0045](0045-engine-generation-lifecycle-and-staging-exclusions.md));
CF-18.04 shipped engine-native `update`
([ADR 0046](0046-engine-native-update-application.md)); CF-18.05 preserved the
legacy Copier route and rejected preview-era projects
([ADR 0047](0047-legacy-copier-retention-and-preview-transition.md)); CF-18.06
completed the installed-console acceptance matrix and rewrote the user guide
for the shipped behaviour
([ADR 0048](0048-installed-cutover-acceptance-evidence.md)).

Nothing was published. PyPI's latest `create-forge` was `0.3.2` and the
newest tag was `v0.3.2`, so `0.4.0` — the cutover release
[docs/engine-cutover-acceptance.md](../engine-cutover-acceptance.md) fixed —
existed only as a decision. **CF-ROADMAP-01-AC-07** makes an unpublished,
unverified release a blocker on closing the roadmap, and the acceptance
contract's release-sequencing gate 5 additionally requires the reviewed
`forge-template 0.5.0` release paired with the candidate client to pass the
full cross-repository matrix — the provider-owned half of that
([FT-18.01](https://github.com/Sandsy09/forge-template/issues/156)) is a
separate issue in the other repository, still open when this ADR is accepted.

The gap between "implemented on `main`" and "published" had also gone stale in
the repository's own prose, not just in the roadmap bookkeeping: the root
`README.md` — which doubles as the PyPI project description — still told
users to run `uvx create-forge@0.3.2`, described Copier as the renderer, kept
a "Preview: more project types" section built on the removed
`--engine-preview` flag, and closed with "no release is scheduled yet";
`compat.INTEGRATION_LINE` still reported `"v0.3.x-engine"` from `doctor`; and
[tests/test_cutover_acceptance_contract.py](../../tests/test_cutover_acceptance_contract.py)
carried one surviving tripwire naming this issue as the one to flip it.

## Decision

1. **Ship `0.4.0` as the cutover release, and mark it breaking.** The default
   `new` architecture and the resolved dependency set both change from the
   `0.3.x` line — the engine is required, `copier` is optional. The release
   PR carries the `breaking-change` label and the GitHub release notes carry
   a migration section, matching
   [docs/engine-cutover-acceptance.md § The cutover release](../engine-cutover-acceptance.md#the-cutover-release)'s
   own rule. This is not `1.0.0`; whether a later release promotes the engine
   to `1.0.0` stays an explicitly later decision, as it does for
   `forge-template`.

2. **Move `compat.INTEGRATION_LINE` to `"v0.4.x-engine"` deliberately, not by
   derivation.** It is a shipped diagnostic surface —
   `doctor --json`'s `integration.line` — reviewed by hand exactly as ADR
   0040 and CF-18.01 reasoned when the constant was introduced;
   `tests/test_engine_contract.py`'s
   `test_diagnostic_integration_line_matches_package_release_line` continues
   to enforce that the literal's major/minor tracks `pyproject.toml`'s own.

3. **Split the work into two phases across the FT-18.01 gate.** A Phase A PR
   does everything this repository owns that does not require a published
   release: the version bump, the diagnostic-line change, every test and
   document this makes stale, and a skeleton evidence record. It merges to
   `main` without dispatching `release.yml`. Phase B — the dry run, the real
   dispatch, the seven-check published-artefact audit, and closing the
   roadmap — starts only once FT-18.01 has landed, satisfying gate 5 and
   **CF-ROADMAP-01-AC-07**. This mirrors ADR 0034's own release/verify split,
   widened by one more gate this cutover's cross-repository dependency
   requires that the Data Science release did not have.

4. **Verify against the published artefacts, recorded verbatim, at the same
   depth as `0.3.0`.** A clean environment installs `create-forge==0.4.0`
   through all four contractual install modes and reproduces engine
   generation of Library, CLI Application, and Data Science, the `--legacy`
   Copier route, and an engine-native `update` round-trip — each with the
   generated project's own `uv run --locked poe check` — plus the `0.3.2`
   pin-back the support window promises. The real command output lands in
   `docs/release-0-4-0-validation.md`. No new test module: a PyPI-resolving
   suite would make CI depend on PyPI availability and duplicate the
   candidate-wheel suites byte for byte, the same reasoning ADR 0034 gave.

5. **Reconcile roadmap bookkeeping in prose and the evidence record only —
   never the filing manifest or the checker.**
   `scripts/check_roadmaps.py` has no "complete" pack status: `PACK_STATUSES`
   is `{prepared-not-filed, filed-open}`, it requires a single status shared
   with roadmap-v4 (which stays `filed-open`), it requires
   `status:blocked` to track `blocked_by` exactly, and it requires an
   unchecked `- [ ] ` box in every filed body. Inventing a `filed-closed`
   status would touch the manifest, all 24 sha256-pinned issue bodies, the
   live GitHub bodies, and the byte-identical `forge-template` mirror of the
   script itself — disproportionate to what closing one roadmap needs.
   Instead: `docs/release-0-4-0-validation.md` carries a roadmap
   reconciliation table (the ADR 0034 / `release-0-3-0-validation.md`
   pattern), the two roadmap-v3 Status paragraphs move from "filed and open"
   to "filed and delivered" pointing at that record, and the GitHub epic,
   issue, and Stage 18 milestone close normally. The pack itself — manifest,
   bodies, `ISSUE-INDEX.md`, and the checker's expected output — stays
   byte-identical.

6. **Record this as its own ADR and canonical doc, and retire the last
   tripwire.** `docs/release-0-4-0-validation.md` maps the release identity,
   published verification, and roadmap reconciliation to their evidence,
   linked from `docs/README.md`'s Validation records table with a
   link-audit case in `tests/test_engine_contract.py`, the same house style
   ADR 0048 established.
   `tests/test_cutover_acceptance_contract.py`'s
   `test_tripwire_version_is_not_yet_the_cutover_release` — the only
   surviving tripwire — is replaced with a derived assertion that the
   diagnostic line and the acceptance contract's own Status section now
   describe the published state, the same "flip the tripwire into a derived
   check" move CF-18.06 made for its two.

7. **The `0.3.x` support window starts at this publication, not later.**
   `create-forge 0.3.x` stays installable and supported for at least 90 days
   and at least one further tagged release past this one
   ([docs/engine-cutover-acceptance.md § Rollback and support
   windows](../engine-cutover-acceptance.md#rollback-and-support-windows)).
   `docs/user-guide/migration.md`'s `create-forge==0.3.2` pin-back recipe and
   its guards (`tests/test_user_guide_recipes.py`,
   `tests/test_e2e_installed_cutover.py::test_recipe_pin_back_to_0_3_x`) are
   not stale pre-cutover content to correct — they are the commitment this
   release starts the clock on, and they stay as written.

## Consequences

- `pyproject.toml`'s `version` moves to `0.4.0`; `compat.INTEGRATION_LINE`
  moves to `"v0.4.x-engine"`. No other shipped module, dependency range, CLI
  flag, or protocol changes beyond what CF-18.01–18.06 already merged.
- `create-forge 0.4.0` is on PyPI, tag `v0.4.0` is on `main`, and the GitHub
  release is published, with a migration section naming the breaking change.
  A published PyPI version is immutable: any defect found after publication
  is corrected forward as `0.4.1`, with the defective version yanked — never
  a re-upload.
- `docs/release-0-4-0-validation.md` is new. `CLAUDE.md`, `README.md`,
  `docs/engine-cutover-acceptance.md`, `docs/integration-contract.md`,
  `docs/cli-conventions.md`, `docs/engine-default-cli.md`,
  `docs/engine-cutover-validation.md`, and `docs/cross-repository-workflow.md`
  retire their "not yet published" / "pre-cutover" voice for the shipped
  state, in the same change as this ADR's Phase A half.
- CF-18.07 closes, CF-EPIC-18 closes, and the Stage 18 milestone closes. The
  Engine-Default Cutover roadmap is complete; the next roadmap is Streamlit
  ([`docs/roadmap-v4`](../roadmap-v4/README.md)), gated on its own provider
  stages.
- This ADR does not itself implement, provision, or validate any provider
  behaviour — `forge-template`'s Stage 18 evidence stays FT-18.01's, exactly
  as **CF-ROADMAP-01-EX-01** requires.
