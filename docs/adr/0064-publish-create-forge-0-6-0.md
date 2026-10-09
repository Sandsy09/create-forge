# 64. Publish create-forge 0.6.0 and close the batch roadmap's client work

## Status

Accepted

## Context

[Issue #206 / CF-29.03](https://github.com/Sandsy09/create-forge/issues/206)
is the last child of
[CF-EPIC-29](https://github.com/Sandsy09/create-forge/issues/192). Everything it
depends on has landed on `main`: CF-29.01 adopted the reviewed
`forge-template 0.7.0` batch provider line
([ADR 0061](0061-adopt-the-0-7-batch-provider-line.md)); CF-29.02 proved installed
batch generation, install modes, Windows and non-UTF-8 lanes, update, and the
released-client comparison through the real console
([ADR 0062](0062-validate-batch-through-the-installed-candidate.md)); and the
`uv` floor was raised past a published advisory before this release, as
CONTRIBUTING requires ([ADR 0063](0063-raise-the-uv-floor-to-0-12-18.md)).

None of it is published. `create-forge 0.5.0` declares `forge-template>=0.6,<0.7`
and cannot select `batch`: it rejects `forge-template 0.7.0` with exit `3`. The
properties of the release machinery that [ADR 0056](0056-publish-create-forge-0-5-0.md)
recorded still hold, and shape what follows:

- `release.yml` runs **no tests** and tags whatever `main` is when it is
  dispatched. It computes the tag from `pyproject.toml`, requires a `[X.Y.Z]`
  `CHANGELOG.md` section, checks the wheel, tags, creates the GitHub release, and
  a separate job publishes to PyPI.
- The `pypi` environment has **no protection rules**, so a real dispatch publishes
  immediately, and a published version can never be replaced.
- The live documentation deploys from `main` the moment a `docs/user-guide/**`
  change merges. The batch page is excluded from the site until this release
  (ADR 0062 decision 8) so the guide never leads the package.

`compat.INTEGRATION_LINE` is tied to the package's minor version on purpose
(`doctor --json`'s `integration.line`): client `0.N.x` pairs with provider
`0.(N+1)`, so provider `0.7` pairs with client `0.6`. The integration contract's
`v0.5.x` row currently reads `>=0.7,<0.8` and "unreleased" (written by CF-29.01
while the range was ahead of the published release); at release it must return to
what published `0.5.0` actually declares.

A fact about the generated release notes also shapes the plan: `git-cliff` omits
`chore:` commits, and the adoption was a `chore:` (as CF-21.01's was). The
generated `0.6.0` notes list the refactors, fixes, documentation and tests, but
never say that `batch` exists.

## Decision

1. **Ship `0.6.0`, on a new line `v0.6.x-engine` paired with
   `forge-template>=0.7,<0.8`.** The provider moves a minor line, so the client
   does too, and `INTEGRATION_LINE` moves by hand, not by derivation, exactly as
   ADRs 0049 and 0056 did; the existing
   `test_diagnostic_integration_line_matches_package_release_line` keeps the
   literal honest. The compatibility tables are corrected in the same change: the
   `v0.5.x` row returns to `>=0.6,<0.7` (what `0.5.0` actually published) and a
   new `v0.6.x` row is the current line. This is **not** a breaking release: the
   provider moves only its package version and the discovered catalogue
   (ADR 0061), and no protocol tuple, `metadata_version` or facade changes.

2. **Two phases, with the documentation after publication.** Phase A is the
   release PR: the version, the line, every test and contract it makes stale, the
   changelog section, and this record. It changes no user-guide file, `README.md`
   or `mkdocs.yml`, so nothing deploys to the live site. Phase B publishes the
   batch guide and the release record only after PyPI serves the version and the
   published artefacts are verified, because that PR is what deploys the site. This
   is ADR 0049's and ADR 0056's split.

3. **`main` is frozen between the release PR and the release.** The three open
   Dependabot bumps were merged first, one at a time, each rebased onto current
   `main` and read against its own CI, and the `uv` floor PR landed before the
   release PR, so the tagged commit is the commit that passed the protected CI.
   The dry run prints the tag and the notes but not the commit, so its run
   `headSha` must equal the commit whose CI validated it, checked before both the
   dry run and the real dispatch.

4. **The irreversible step has an explicit human gate.** Everything up to and
   including the dry run, which creates nothing, runs without one. The real
   dispatch is made only after the maintainer confirms it directly beforehand,
   because it tags, releases and publishes with no other approval, and its only
   recovery is a yank and a patch release.

5. **The installed suites run against the published wheel.** After publication the
   update-safety, batch and Streamlit suites are run against the wheel downloaded
   from PyPI, not a rebuild of the tree, using the opt-in
   `CREATE_FORGE_CANDIDATE_WHEEL=<path>` that ADR 0056 added (checked rather than
   trusted: a missing file, a non-wheel or another version fails loudly instead of
   falling back to a build). Archive hashes are not a stable identity across build
   environments (ADR 0054), so the published wheel is compared with the candidate by
   **content digest** (`scripts/candidate_evidence.py --archive PATH`); the archive
   sha256 of the published file is recorded as what PyPI serves.

6. **Verify the published artefacts by hand as well, and record it verbatim.**
   Identity (tag to commit, the GitHub release, PyPI files, the declared dependency
   range, `templates.toml` in the wheel), the install modes from PyPI, generation of
   each archetype **including `batch`** with the generated project's own
   `uv run --locked poe check` and `uv run poe run`, a `--legacy` round trip, an
   engine-native `update --dry-run`, and the `0.5.0` pin-back. The output lands in
   `docs/release-0-6-0-validation.md` in Phase B, written after publication. No
   PyPI-resolving test module joins the suite: CI must not depend on PyPI
   availability.

7. **State the headline in the GitHub release body.** Because `git-cliff` omits
   `chore:` commits, the generated notes would not mention `batch`. As for `0.5.0`,
   a hand-written **Highlights** section is prepended to the release body after
   publication; the generated `CHANGELOG.md` is left exactly as generated.

8. **Reconcile the roadmap in prose and the record only.** `docs/roadmap-v5/**` is
   mirrored byte for byte from `forge-template` ([docs/roadmap-tracking.md](../roadmap-tracking.md)),
   so the pack stays identical. The GitHub issue and epic close with the release receipts; the
   milestone is left to the maintainer.

## Consequences

- `pyproject.toml`'s `version` and `uv.lock` move to `0.6.0`;
  `compat.INTEGRATION_LINE` moves to `"v0.6.x-engine"`. No shipped module other
  than that constant changes, so the update-safety source digest (ADR 0054), which
  covers `paths.py`, `update.py`, `staging.py` and four functions in
  `commands/update.py`, is untouched and the installed update-safety evidence still
  binds this candidate.
- `CHANGELOG.md` is regenerated with `git-cliff`, as the release procedure says.
  The tool moved from 2.13 to 2.14 since the last release, which now orders the
  group headings differently in every historical section, so the diff shows older
  releases reordered. No entry was lost: all 87 pre-existing bullets are present
  and none is duplicated.
- Until the release is dispatched, `main`'s contract tables describe `0.6.0` as
  released, and `CLAUDE.md` says `0.5.0` is still the latest published version. The
  release follows the merge immediately and `main` is frozen in the meantime; if the
  release were abandoned, that wording would be reverted rather than left standing.
- `create-forge 0.6.0` on PyPI, tag `v0.6.0` and its GitHub release, once
  dispatched, are immutable: a defect found afterwards is corrected forward as
  `0.6.1` with `0.6.0` yanked, never re-uploaded. `create-forge 0.5.x` keeps
  declaring the `0.6` provider line and stays installable; it rejects
  `forge-template 0.7.0` by design.
- `docs/release-0-6-0-validation.md` and the batch guide's publication are
  Phase B, gated on the published artefacts and not on this record.
- This ADR does not change the `pypi` environment's missing protection rules, the
  CI `UV_VERSION` scanner pin, or the three install hints that still quote the old
  `uv` range (ADR 0063 decisions 4 and 5); those are separate concerns, raised with
  the maintainer rather than changed here.
