# 56. Publish create-forge 0.5.0 and close the Streamlit roadmap's client work

## Status

Accepted

## Context

[Issue #167 / CF-21.03](https://github.com/Sandsy09/create-forge/issues/167)
is the last child of
[CF-EPIC-21](https://github.com/Sandsy09/create-forge/issues/154). Everything it
depends on has landed on `main`: CF-21.01 adopted the reviewed
`forge-template 0.6.0` Streamlit provider line
([ADR 0050](0050-adopt-the-0-6-streamlit-provider-line.md)); CF-21.02 proved
installed Streamlit generation through the real console
([ADR 0051](0051-validate-installed-streamlit-generation.md)); and the safety
epic made the update path contained
([ADR 0052](0052-contain-every-client-filesystem-target.md)), recoverable
([ADR 0053](0053-recover-updates-from-the-actual-git-state.md)), evidence-bound
([ADR 0054](0054-verify-installed-update-safety-on-the-release-candidate.md)) and
decoding-safe ([ADR 0055](0055-capture-subprocess-output-as-bytes-and-decode-by-rule.md)).

None of it is published. `create-forge 0.4.0` declares `forge-template>=0.5,<0.6`
and cannot select Streamlit. Three properties of the release machinery shape what
follows:

- `release.yml` runs **no tests** and tags whatever `main` is when it is
  dispatched. It computes the tag from `pyproject.toml`, requires a `[X.Y.Z]`
  `CHANGELOG.md` section, checks the wheel, tags, creates the GitHub release, and
  a separate job publishes to PyPI.
- The `pypi` environment has **no protection rules**, so a real dispatch publishes
  immediately, and a published version can never be replaced.
- The live documentation deploys from `main` the moment a `docs/user-guide/**`
  change merges. The Streamlit page is excluded from the site until this release
  (ADR 0051) so the guide never leads the package.

`compat.INTEGRATION_LINE` is tied to the package's minor version on purpose
(`doctor --json`'s `integration.line`): the pairing so far is client `0.N.x` with
provider `0.(N+1)`. The integration contract's `v0.4.x` row had drifted to claim
`>=0.6,<0.7` for a line whose published release declares `>=0.5,<0.6`.

## Decision

1. **Ship `0.5.0`, on a new line `v0.5.x-engine` paired with
   `forge-template>=0.6,<0.7`.** The provider moves a minor line, so the client
   does too, and `INTEGRATION_LINE` moves by hand, not by derivation, exactly as
   ADR 0049 did for `v0.4.x-engine`; the existing
   `test_diagnostic_integration_line_matches_package_release_line` keeps the
   literal honest. The three compatibility tables are corrected in the same
   change: `v0.4.x` returns to `>=0.5,<0.6` (what `0.4.0` actually published) and
   `v0.5.x` is the current line. This is **not** a breaking release and claims no
   cutover: the provider moves only its package version and the discovered
   catalogue, and no protocol tuple, `metadata_version` or facade changes.

2. **Two phases, with the documentation after publication.** Phase A is the
   release PR: the version, the line, every test and contract it makes stale, the
   changelog section, the harness change in decision 5, and this record. It
   changes no user-guide file, so nothing deploys to the live site. Phase B
   publishes the Streamlit guide and the release record only after PyPI serves the
   version and the published artefacts are verified, because that PR is what
   deploys the site. This is ADR 0049's split, with the gate moved from a
   provider issue to the published-artefact audit.

3. **`main` is frozen between the release PR and the release.** Dependabot's
   three open bumps were merged first, one at a time, so the tagged commit is the
   commit that passed the protected CI. The dry run's run `headSha` must equal the
   commit whose CI validated it, because the dry run prints the tag and the notes
   but not the commit.

4. **The irreversible step has an explicit human gate.** Everything up to and
   including the dry run, which creates nothing, runs without one. The real
   dispatch is made only after the maintainer confirms it directly beforehand,
   because it tags, releases and publishes with no other approval, and its only
   recovery is a yank and a patch release.

5. **The installed suites run against the published wheel.** After publication the
   update-safety and Streamlit suites are run against the wheel downloaded from
   PyPI, not a rebuild of the tree. `tests/conftest.py`'s `candidate_wheel`
   honours an opt-in `CREATE_FORGE_CANDIDATE_WHEEL=<path>`, checked rather than
   trusted (a missing file, a non-wheel or another version fails loudly instead of
   falling back to a build), and `scripts/candidate_evidence.py --archive PATH`
   prints an archive's sha256 and content digest. Archive hashes are not a stable
   identity across build environments (ADR 0054), so the published wheel is
   compared with the candidate by **content digest**; the archive sha256 of the
   published file is recorded as what PyPI serves. Unset, the fixture is unchanged.

6. **Verify the published artefacts by hand as well, and record it verbatim.**
   Identity (tag to commit, the GitHub release, PyPI files, the declared
   dependency range, `templates.toml` in the wheel), the install modes, generation
   of each archetype including Streamlit with the generated project's own
   `uv run --locked poe check`, a `--legacy` round trip, an engine-native
   `update --dry-run`, and the `0.4.0` pin-back. The output lands in
   `docs/release-0-5-0-validation.md` in Phase B, written after publication like
   `release-0-4-0-validation.md`. No PyPI-resolving test module joins the suite:
   CI must not depend on PyPI availability.

7. **Reconcile the roadmap in prose and the record only.** `docs/roadmap-v4/**` is
   hash-pinned and its checker has no "complete" status (ADR 0049 decision 5), so
   the pack stays byte-identical. The GitHub issue, the epic and the milestone
   close through the maintainer, with no cutover claim.

## Consequences

- `pyproject.toml`'s `version` and `uv.lock` move to `0.5.0`;
  `compat.INTEGRATION_LINE` moves to `"v0.5.x-engine"`. No shipped module other
  than that constant changes, so the update-safety source digest (ADR 0054) is
  untouched and the installed update-safety evidence still binds this candidate.
- Until the release is dispatched, `main`'s contract tables describe `0.5.0` as
  released. The release follows the merge immediately and `main` is frozen in the
  meantime; if the release were abandoned, that wording would be reverted rather
  than left standing.
- `create-forge 0.5.0` on PyPI, tag `v0.5.0` and its GitHub release, once
  dispatched, are immutable: a defect found afterwards is corrected forward as
  `0.5.1` with `0.5.0` yanked, never re-uploaded. `create-forge 0.4.x` keeps
  declaring the `0.5` provider line and stays installable.
- `docs/release-0-5-0-validation.md` and the Streamlit guide's publication are
  Phase B, gated on the published artefacts and not on this record.
- This ADR does not change the `pypi` environment's missing protection rules; that
  is a separate concern, raised with the maintainer rather than changed here.
