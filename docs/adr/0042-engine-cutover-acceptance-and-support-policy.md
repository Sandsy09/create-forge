# 42. Approve the engine-default cutover acceptance and support policy

## Status

Accepted

## Context

[ADR 0040](0040-engine-default-selection-and-source-resolution.md) fixed the
post-cutover CLI *selection and source-resolution* surface and
[ADR 0041](0041-engine-project-lifecycle-and-update-dispatch.md) fixed the
*`new` lifecycle and `update` dispatch* surface. Each deferred, by name, the
same short list to CF-16.03 / #157: the concrete cutover version numbers, the
support and deprecation windows, the cross-repository acceptance matrix, and
the evidence owners. ADR 0040's "Deprecation sequencing" preamble and both
canonical contracts' "What this contract does not decide" sections point here.

The provider side is settled and immutable-pinned.
`forge-template`'s
[cutover-compatibility-and-acceptance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)
(FT-15.04 / forge-template ADR 0061) fixes the engine at `0.5.0` — deliberately
not `1.0.0` — with component-manifest protocol moving `(1, 2)` to `(1, 2, 3)`,
a published `metadata_version = 1`, and every other versioned axis unchanged;
an immutable-forward-plus-yank release-rollback rule; a `0.4.x` support window
of at least 90 days and at least one further tagged release past the cutover;
and an acceptance matrix whose two `create-forge`-executed rows are left as
bare phrases. `forge-template`'s
[compatibility-policy.md](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md)
owns the 90-day / one-release deprecation window for every provider axis;
changing that number needs an ADR superseding forge-template ADR 0041, so this
decision cites it and never restates or alters it.

Nothing in either repository currently states `create-forge`'s own supported
operating systems, Python versions, or install modes — `forge-template`'s
[python-support.md](https://github.com/Sandsy09/forge-template/blob/main/docs/python-support.md)
explicitly disclaims covering the CLI. That gap, the concrete client version,
and the windows are what this decision closes.

CF-16.03 blocks
[FT-17.01](https://github.com/Sandsy09/forge-template/issues/150),
[FT-17.02](https://github.com/Sandsy09/forge-template/issues/151), the whole
[FT-EPIC-17](https://github.com/Sandsy09/forge-template/issues/142), and — in
roadmap-v4 —
[FT-19.01](https://github.com/Sandsy09/forge-template/issues/157), the Streamlit
entry gate. It is the last contract gate before the provider implementation
stage begins.

This is a decision issue. It records the contract in
[`docs/engine-cutover-acceptance.md`](../engine-cutover-acceptance.md) and
updates the living contracts it touches. It changes no runtime code, moves no
dependency, bumps no version, requires no `forge-template` change, files no
GitHub issue, and edits no byte-pinned `docs/roadmap-v3/**` file. Every
implementing step is an already-filed
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153) /
[FT-EPIC-18](https://github.com/Sandsy09/forge-template/issues/143) child, and
the matrix closes **CF-ROADMAP-01-AC-06** by reference, exactly as
forge-template ADR 0061 decision 4 closed its own bounded-issue rows.

Its review obligations are **CF-ROADMAP-01-AC-06** (implementation, migration
E2E, legacy regression and release tasks are filed separately with an explicit
dependency graph — shared with
[CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) and
[CF-18.07](https://github.com/Sandsy09/create-forge/issues/164)) and
**CF-ROADMAP-01-EX-04** (no implementation or release in this decision issue —
owned solely by CF-16.03).

## Decision

1. **Perform the cutover in one tagged release, `create-forge 0.4.0`.** A
   single minor bump on the `0.x` line makes the engine the default `new`
   path, moves `forge-template` into `[project.dependencies]` and `copier`
   into the optional `legacy` extra, removes `--engine-preview`, adopts
   `forge-template>=0.5,<0.6`, and ships the engine `new` lifecycle and the
   engine-native `update` route. It mirrors the provider's `0.3.2 → 0.4.0`
   Data Science precedent and its stated reasoning for `0.5.0` over `1.0.0`.
   Rejected: `1.0.0` (declares the CLI stable and switches its compatible-range
   rule from minor-scoped to major-scoped for every future consumer, before
   Stage 18 has validated the integrated cutover — the exact reason the
   provider declined `1.0.0` for itself); a staged `0.4.0`-then-`0.5.0` pair
   (CF-EPIC-18 files exactly one release child, CF-18.07, and a second would
   need a filed issue this roadmap does not have).

2. **Correct a defective release forward and yank it, never mutate it.** A
   published `create-forge` release is immutable; a `0.4.0` defect is fixed
   forward as `0.4.1` (or a new line) and the defective version is yanked from
   PyPI so no new install resolves it. This matches `release.yml`, which
   already rejects an existing or non-increasing tag. Rolling back a user's
   generated project after a bad update is the clean-tree precondition and the
   printed `git restore` / `git clean` recovery ADR 0041 fixed, implemented by
   [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) /
   [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162), not a
   release-process concern. Rejected: fix-forward without yanking (leaves a
   known-bad `uvx create-forge@0.4.0` resolvable indefinitely); yanking only
   for data-loss or security defects (narrower than the provider's rule for no
   reason the client's added Git and merge surface justifies).

3. **Support `create-forge 0.3.x` for at least 90 days and at least one
   further tagged `create-forge` release past the cutover.** `create-forge
   0.3.2` resolves `forge-template>=0.4.1,<0.5`, so pinning `create-forge==0.3.2`
   is a documented, tested recovery path for a user who hits a `0.4.0` defect;
   the acceptance matrix carries the row proving it still resolves, installs
   and generates after `0.4.0` publishes. This is a new client-side commitment
   modelled on `forge-template`'s `0.4.x` window, not an inheritance. Rejected:
   a release-count floor with no calendar minimum (a fast follow-up release
   could close the window in days); no formal window (leaves a user with no
   stated fallback for a cutover-release defect).

4. **Give any later-retired visible surface a deprecation warning naming its
   replacement, for at least 90 days and at least one further tagged
   `create-forge` release.** Notice is layered through this contract's support
   statements, a tracking issue and pull request, the CLI's own warning text,
   and the release notes. This is the shape `forge-template`'s
   compatibility-policy.md already commits to, so the two repositories state
   one number; `create-forge` cites that policy rather than restating it.
   Rejected: one release with no calendar minimum (a rapid patch could satisfy
   it in a day); two releases and 90 days (stricter than the provider on the
   release count, out of step with the sibling repo).

5. **Remove `--engine-preview` in `0.4.0` with no window, and start no
   deprecation clock on the direct-Copier route.** `--engine-preview` is
   hidden, `--help`-absent and documented development-only, so it has no
   compatibility promise (restates ADR 0040 decision 34). `--legacy`,
   `--template`, `--template-url`, `--ref`, the bundled registry and
   `create-forge update` against a `.copier-answers.yml` project all stay
   supported and undeprecated (restates ADR 0040 decision 33), because
   `forge-template` guarantees `template/`, `copier.yml` and `copier update`
   remain live.

6. **Express every window relative to publication, with no calendar date.**
   Days elapsed and releases tagged, because `create-forge` releases are
   irregular and manually triggered — the same reason `forge-template` gives.
   This satisfies CF-16.03's "do not preselect deprecation dates" exclusion:
   the policy is fixed, no date is invented.

7. **Claim Linux and Windows as supported and proven; treat macOS as expected
   to work with no support claim.** The cutover newly makes the CLI run
   `git init`, `git commit` and `pre-commit install` and merge a working tree,
   so the acceptance matrix requires an explicit `windows-latest` run of the
   engine `new` finalisation ([CF-18.03](https://github.com/Sandsy09/create-forge/issues/160))
   and the engine-native update
   ([CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)) — coverage
   today's Windows fast-suite job does not give, because `e2e` runs on
   `ubuntu-latest` only. Rejected: adding a macOS CI runner (neither repository
   has one and the cross-repo matrix would stay asymmetric); declaring macOS
   unsupported (refuses support that probably works for a plausible real user).

8. **Adopt the latest-four-final-CPython-releases window as `create-forge`'s
   own Python support policy** — today 3.11 through 3.14. `requires-python`'s
   floor is the oldest active release, the classifiers enumerate the window,
   and the CI matrix is the window; admitting or retiring a release follows
   the same evidence gate `forge-template` uses and the decision-4 notice
   period. This is the CLI's own copy of the rule `forge-template`'s
   python-support.md applies to generated projects but disclaims for the CLI.
   The floor does not move at the cutover — nothing in the engine path
   requires it and `forge-template`'s own floor is `>=3.11`. Rejected: keeping
   `>=3.11` with no policy commitment (leaves "when does 3.11 drop" unanswered
   where CF-16.03 was asked to answer it); raising the floor at the cutover
   (makes the client stricter than the provider for no evidenced reason).

9. **Make four install modes contractual**, each with an acceptance-matrix row:
   `uvx create-forge`, `uv tool install create-forge`, `pip install
   create-forge` into an environment, and `create-forge[legacy]` through any of
   them. `pip` becomes a documented, tested mode because ADR 0040's accepted
   diagnostics already print `pip install 'create-forge[legacy]'` as a remedy.
   Rejected: uv-only (would leave ADR 0040's remedy string naming an
   unsupported mode); adding `pipx` (appears nowhere in either repository and
   adds a proof row for a path nobody has asked for).

10. **Record the cross-repository acceptance matrix in the provider's shape.**
    Sectioned tables — default engine generation, engine-source overrides,
    engine generation finalisation, engine-native update, legacy Copier route,
    preview-project transition, failure paths, cross-repository integrated
    validation, publication — each row one non-interactive check, one evidence
    command, one owning issue, and the Stage 18 child it is first required at.
    Every owner is an already-filed issue
    ([CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)–07,
    [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156)); the
    matrix names the concrete `create-forge`-side command for the two rows the
    provider matrix left as bare phrases. The guard test checks both
    directions: every row names a filed issue, every Stage 18 client child owns
    at least one row.

11. **State release sequencing as gates that point at, not duplicate, the
    provider's gate table.** Provider publishes the reviewed immutable
    `forge-template 0.5.0` first (FT-17.06); `create-forge` adopts the range
    (CF-18.01); both integrated validations (FT-18.01 and CF-18.06) and working
    engine-native **and** legacy updates pass before `create-forge 0.4.0` is
    published (CF-18.07, **CF-ROADMAP-01-AC-07**); a provider defect requires a
    corrected reviewed release and renewed adoption evidence.
    [`docs/integration-contract.md`](../integration-contract.md)'s release
    coordination section stays authoritative for the client-side mechanics.

12. **Publish the contract as `docs/engine-cutover-acceptance.md`.** A new
    canonical living document in the idiom of
    [`docs/engine-default-cli.md`](../engine-default-cli.md) and
    [`docs/engine-project-lifecycle.md`](../engine-project-lifecycle.md), the
    client-side mirror of `forge-template`'s
    cutover-compatibility-and-acceptance.md. It is linked from `CLAUDE.md`,
    `CONTRIBUTING.md` and [`docs/cli-conventions.md`](../cli-conventions.md);
    `docs/engine-default-cli.md`, `docs/engine-project-lifecycle.md`,
    `docs/engine-updates.md` and `docs/integration-contract.md` gain pointers
    and have their "deferred to CF-16.03" language resolved. The
    `cli-conventions.md` exit-status table and the `integration-contract.md`
    compatibility table are untouched — nothing here moves a range or a
    status.

13. **Close CF-EPIC-16 with this decision.** Its children are CF-16.01, CF-16.02
    and CF-16.03; "every child complete" means those three. For
    **CF-ROADMAP-01-AC-06** and **CF-ROADMAP-01-AC-07** the epic's slice is
    that the implementation, migration-E2E, legacy-regression and release work
    is filed with an explicit dependency graph
    ([CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)–07 plus
    [`CROSS-REPO-DEPENDENCIES.md`](../roadmap-v3/github-issues/CROSS-REPO-DEPENDENCIES.md))
    and that this contract implements and releases nothing — both true on
    merge. The CF-18.x and FT-18.x delivery slices stay open under CF-EPIC-18.

## Consequences

- `docs/engine-cutover-acceptance.md` is added and linked from `CLAUDE.md`,
  `CONTRIBUTING.md`, and `docs/cli-conventions.md`;
  `tests/test_engine_contract.py` gains a link-audit guard copying the existing
  ones.
- `tests/test_cutover_acceptance_contract.py` is added: derived assertions
  against the live pre-cutover repository (`create-forge` still on the `0.3`
  line, `requires-python` still `>=3.11`, classifiers still 3.11–3.14, no
  `legacy` extra), a structural check that every acceptance-matrix row names an
  issue in the roadmap `filing-manifest.json` and every Stage 18 client child
  owns a row, and tripwires that fail deliberately when CF-18.01 / CF-18.06 /
  CF-18.07 land. It also asserts this record names `CF-ROADMAP-01-AC-06` and
  `CF-ROADMAP-01-EX-04` literally.
- `docs/engine-default-cli.md`, `docs/engine-project-lifecycle.md`,
  `docs/engine-updates.md`, and `docs/integration-contract.md` have their
  "concrete versions, windows, matrix and dates are CF-16.03's" language
  replaced with a reference to this resolved contract. The
  `integration-contract.md` compatibility table and the `cli-conventions.md`
  exit-status table are untouched — no range moves and no status changes here.
- `forge-template` FT-17.01 and FT-17.02, `FT-EPIC-17`, and roadmap-v4's
  FT-19.01 are unblocked: their `create-forge` contract gate is cleared.
- CF-EPIC-16 is closed. Its three children have reviewed completion evidence;
  its mapped acceptance criteria are satisfied by their named owners or, for
  the delivery-stage criteria, filed with an explicit dependency graph.
- The cutover this contract describes is still unbuilt. This ADR files no
  issue, ships no code, moves no dependency, bumps no version, and performs no
  release — CF-EPIC-18 performs the cutover, and until it does the engine path
  stays behind `--engine-preview` and `create-forge` stays on the `0.3` line.
