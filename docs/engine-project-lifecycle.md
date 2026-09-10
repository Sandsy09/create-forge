# Engine Project Lifecycle

This is the living contributor contract for what `create-forge` does to a
project on disk **after the engine renders it** and **when the user later runs
`create-forge update`** — the post-render Git and hook lifecycle, the
generation-metadata file the client persists, and how an engine-native update
routes, merges, previews, and rolls back. It is the update-and-lifecycle
counterpart to [`docs/engine-default-cli.md`](engine-default-cli.md)'s
selection-and-source-resolution surface.

It decides no runtime behaviour and ships nothing. Like its predecessor
contracts on both sides of the boundary, it introduces no protocol increment,
no new component, no `copier.yml` change, and no package version bump. The
*rules* below are the contract; the releases that implement them are
[CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) (engine `new`
finalisation, Git, hooks),
[CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) (engine-native
update), and
[CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) (legacy and
preview-project transition).

It is a sibling of [`docs/filesystem-generation.md`](filesystem-generation.md)
(which keeps the staging, atomic-rename and cleanup rules, authoritative) and
[`docs/engine-default-cli.md`](engine-default-cli.md), and extends
[`docs/cli-conventions.md`](cli-conventions.md)'s `update` and exit-status
sections. Every semantic rule about the metadata document's *shape*, the
render reproducibility guarantee, the classification vocabulary, and the
per-target regeneration and rename data stays owned by `forge-template`'s
[`generation-provenance.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md)
(FT-15.02, forge-template ADR 0059).

## Status

Accepted as a contract under
[ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md), the
second child of
[CF-EPIC-16 / #152](https://github.com/Sandsy09/create-forge/issues/152). Its
design gate is the four accepted `forge-template` Stage 15 contracts and
CF-16.01 ([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md)),
all merged.

**This contract is not the cutover.** No `create-forge` release named here
exists yet. Until [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160)
onward implement it, the engine path is reachable only through the hidden
`new --engine-preview` flag — which writes no `.git`, installs no hooks, and
writes no generation metadata — and `create-forge update` handles only
direct-Copier projects through `runner.update`.
[`docs/filesystem-generation.md`](filesystem-generation.md) and
[`docs/cli-conventions.md`](cli-conventions.md) remain authoritative for
actual behaviour.

The two reserved `forge-template` `EngineErrorCode` values
(`invalid-generation-metadata`, `unsupported-generation-metadata`) are **not
shipped** at this contract's acceptance — FT-17.01 adds them. Nothing here
assumes they exist yet; the client-side "metadata file missing or unreadable"
path (§ Exit statuses) is `create-forge`'s own and stays distinct from them.

## The engine `new` finalisation lifecycle

The engine `new` path renders and validates fully in memory, then stages
adjacent to the destination, resolves `uv.lock`, and finalises by atomic
rename — all unchanged from
[`docs/filesystem-generation.md`](filesystem-generation.md). This contract
adds what happens **after the rename**, at the final destination, to reach
parity with what `forge-template`'s `copier.yml` `_tasks` gives every
direct-Copier project today
([`engine-default-parity.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/engine-default-parity.md)
assigns the `_tasks` row to CF-16.02, `disposition: client` — "the engine
spawns no process").

1. **The lifecycle runs at the final path, not in staging.** `git init`,
   `uv sync`, and `pre-commit install` bake the project's absolute path into
   `.git/hooks/`, `.venv/`, and console-script shims — the same reason the
   direct-Copier path cannot be staged-then-renamed. So the render is staged
   and renamed first (no absolute-path artefacts yet), and only then does the
   lifecycle run against `dst`.

2. **`git init` + one initial commit.** After the rename, `create-forge` runs
   `git init`, `git add -A`, and a single `git commit` whose message matches
   the direct-Copier `_tasks` initial-commit message. `uv.lock` is already
   present from staging (ADR 0021) and is part of that commit, as is the
   `.forge/generation.json` file (below). This is what makes an engine-native
   `update` able to assume a Git repository, exactly as `copier update`
   assumes one.

3. **`pre-commit install` only when a config was rendered.** `create-forge`
   runs `pre-commit install --install-hooks` **only if the render produced a
   `.pre-commit-config.yaml`** — which, on the engine path, happens only when
   the `pre-commit` capability is selected. The client checks for the rendered
   file it already holds; it never inspects a component id
   ([`docs/component-selection.md`](component-selection.md)'s no-allowlist
   rule).

4. **A lifecycle failure keeps the project and warns.** If `git init`, the
   commit, or `pre-commit install` fails after a good render (no Git identity
   configured, `pre-commit` not importable, a hook download that 404s), the
   project is left in place, `create-forge` prints the one manual command that
   finishes the step, and `new` still exits `0`. The render is sound; the
   convenience step is not worth discarding it for. A render, lock, or rename
   failure still cleans up and exits `1`, unchanged — see
   [`docs/filesystem-generation.md`](filesystem-generation.md).

## The generation-metadata file

5. **`.forge/generation.json`, committed.** `create-forge` persists
   `forge-template`'s generation-metadata document as JSON at
   `.forge/generation.json` in the project root, and commits it — to git, in
   the project's own repository, exactly as a direct-Copier project commits
   `.copier-answers.yml`. A committed file is what lets a collaborator or CI
   reproduce or update the project from the same recorded spec. The `.forge/`
   directory (rather than a bare root dotfile) leaves room for future sibling
   state without another top-level entry.

   The document's *shape* is `forge-template`'s
   ([`generation-provenance.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md)):
   `metadata_version`, `provider`, `protocols`, `spec`, `components`,
   `output` (one `{target, owner, digest, regeneration}` per rendered file),
   and `reproduction`. `create-forge` serialises it and writes it; it adds no
   field, and every string leaf traces to the provider's allowlist (no
   timestamp, no absolute path, no environment value).

   `forge-template` ADR 0059 commits FT-17.01 to publish "one documented
   default target" for this file. [ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md)
   asks FT-17.01 to adopt `.forge/generation.json` as that default, so the
   two repositories name one path.

6. **Rewritten on every successful update.** After any successful
   engine-native update `create-forge` rewrites `.forge/generation.json` to
   the new effective spec, component versions, protocol integers, provider
   version, and output digests. It is written **last** (§ Rollback), and left
   staged-but-uncommitted alongside the merged files for the user to review
   and commit. `reproduction.mode` is `"exact"` (or absent) normally, and
   `"degraded"` with a `reason` only on the degraded path (§ Unavailable
   recorded release).

## `update` routing

7. **Route by file; `--legacy` forces Copier.** `create-forge update
   <project>`:

   | Project contains | Route |
   | --- | --- |
   | `.forge/generation.json` | engine-native update (§ below) |
   | `.copier-answers.yml` only | direct-Copier update (`runner.update`, unchanged) |
   | both | engine-native, unless `update --legacy` |
   | `update --legacy` (any of the above) | direct-Copier update |
   | neither | exit `1`, naming both routes |

   The engine-native route never reads or rewrites `.copier-answers.yml`; the
   direct-Copier route never reads `.forge/generation.json`. `--legacy` is the
   same route-selector name `new` uses
   ([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md)).

8. **A pre-cutover `--engine-preview` project is rejected with guidance.**
   Such a project has neither file — the preview wrote no answers file and no
   metadata. `update` exits `1` explaining it was created by the removed
   development-only `--engine-preview` flag, which never supported updates,
   and pointing to regeneration with `create-forge new`. No metadata is
   fabricated and no answers are invented.
   [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) owns the
   exact wording and any migration helper it decides to add.

## Engine-native update

9. **Three file sets, provider-supplied old and new.** An engine-native
   update diffs, keyed by target:

   | Set | Source |
   | --- | --- |
   | **old** | `render_project(recorded spec)` on the recorded `forge-template` release, provisioned into an isolated environment |
   | **new** | `render_project(effective spec)` on the currently installed release |
   | **working tree** | `create-forge` reads it from disk |

   The recorded spec and release come from `.forge/generation.json`. The
   provider guarantees a recorded spec renders byte-identically on its
   recorded release; `create-forge` performs no component-resource read to do
   any of this.

10. **Clean Git working tree required.** The engine-native update refuses to
    start unless the project's Git working tree is clean, exactly as
    `copier update` does. This is what makes § Rollback a `git` operation
    rather than a bespoke snapshot.

11. **Renames are applied to the working tree before diffing.** When
    `.forge/generation.json`'s recorded component versions and the current
    ones straddle an owner-declared `{from, to, since}` rename record, the
    client applies each move to the working tree first, so a user's local
    edits travel with the moved path instead of being stranded
    ([`generation-provenance.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md);
    the catalogue declares none today).

12. **Per-target three-way merge with inline conflict markers.** For each
    target `create-forge` computes the classification
    `forge-template` fixes — `unchanged`, `added`, `removed`, `changed`,
    `renamed` — and merges old / new / working-tree by path. Where a template
    change and a local edit touch the same region, the merged file carries
    inline `<<<<<<<` / `=======` / `>>>>>>>` markers. The result is left
    **staged but uncommitted**; the user reviews it with `git diff`, resolves
    any markers, and commits — the same workflow the direct-Copier route
    already documents.

13. **`removed`: delete only if pristine.** A target present in *old* and
    absent from *new* is deleted from the working tree only if its bytes still
    match *old*'s recorded digest. If it was locally modified, it is left in
    place with a warning that the template no longer manages it; the user
    decides.

14. **`skip-if-exists` targets are never touched on update.** A target whose
    `output` entry records `regeneration: "skip-if-exists"` (today reserved
    for a future `CHANGELOG.md` and `.env`; the engine renders neither yet) is
    never written, merged, or deleted during an update. `create-forge` notes
    it in the summary and moves on — "the engine records the disposition, the
    client applies the skip".

15. **A repeated no-op update changes nothing visible.** When the recorded and
    effective specs are equal and the installed release has not moved, every
    target classifies `unchanged`; `create-forge` detects this before touching
    the working tree, rewrites `.forge/generation.json` to byte-identical
    content (an empty `git diff`), and reports that nothing changed.

## `update --dry-run`

16. **The engine route prints a per-target classification list.** Because the
    engine-native update has *old*, *new*, and the working tree in hand, its
    `--dry-run` is a genuine preview: each affected target with its
    classification (`added` / `changed` / `removed` / `renamed`), marked
    *clean* or *CONFLICT*, and `unchanged` summarised as a count. It writes
    nothing and leaves the Git working tree, index, and `.forge/generation.json`
    untouched.

17. **The direct-Copier route's `--dry-run` is unchanged.** It stays the
    validation-preview `runner.update` already performs with Copier's
    `pretend=True` — Copier's merge cannot report per-file status reliably, so
    that route's dry run does not gain a list.

## Rollback and cancellation

18. **The clean-tree precondition is the rollback.** Because an engine-native
    update starts from a clean Git working tree, recovery from any mid-merge
    failure, render failure, or `Ctrl-C` is `git restore . && git clean -fd`.
    `create-forge` prints that exact command on failure. It does **not** run
    it itself — a tool invoking `git clean -fd` can delete untracked files the
    user cared about; the choice stays the user's.

19. **`.forge/generation.json` is written last.** The refreshed metadata file
    is written only after the merge has fully succeeded. A failed or cancelled
    update therefore never leaves a half-written or inconsistent metadata
    file — the recorded spec still describes the last good state
    (CF-ROADMAP-01-AC-05).

20. **Exit codes.** A cancelled update exits `130`; a merge, render, or
    provisioning failure exits `1`. Both print the recovery hint. See
    § Exit statuses.

## Unavailable recorded release

21. **Fail closed by default.** When the `forge-template` release recorded in
    `.forge/generation.json` cannot be obtained — yanked, offline, an index
    that no longer serves it — `create-forge` fails **before any render or
    write**, with the four report facts
    [`compatibility-policy.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md)
    requires: it names the axis (`provider`), states the detected value (the
    recorded version), and states the required action.

22. **An opt-in degraded two-way update.** `create-forge` may then proceed
    with a degraded update — comparing *new* against the working tree, with
    no *old* render — which loses the ability to distinguish a local edit from
    an old provider default. It is **never automatic**: interactively `update`
    asks, explaining the lost merge base; non-interactively it stays failed
    unless `--degraded` is passed explicitly. When taken, the refreshed
    `.forge/generation.json` records
    `"reproduction": {"mode": "degraded", "reason": …}` so the next update
    knows the merge base was lost.

## `_message_after_update`

23. **One client-owned post-update message, both routes.** `create-forge`
    owns the post-update next-steps text — the `_message_after_update` parity
    row is CF-16.02's, "client update dispatch and messaging". Both routes
    keep today's shape: `Updated. Review the diff before committing —
    conflicts are marked inline.` The engine route additionally reports a
    one-line count of clean versus conflicted targets. A no-op update
    (§ 15) reports that nothing changed instead.

## Exit statuses

The [`docs/cli-conventions.md`](cli-conventions.md) exit-status table stays
authoritative and **unchanged**. Engine-native update failures map onto its
existing rows:

| Condition | Status |
| --- | --- |
| dirty Git working tree; non-Git project; a merge or render failure; `.forge/generation.json` missing when routing chose the engine, or unreadable JSON; neither route file present | `1` |
| the recorded `forge-template` release is incompatible with this CLI, or is unavailable and the degraded path was declined | `3` — the "required generator missing or unusable" class [ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md) already widened `3` to; not a new code |
| the user cancels a prompt or interrupts the merge | `130` |

No new exit code is introduced. The client-side "metadata file missing or
unreadable" case is `create-forge`'s own exit-`1` path and does not use — or
depend on the existence of — `forge-template`'s reserved
`invalid-generation-metadata` code.

## What this contract does not decide

- The `_exclude` staging filter (`copier.yml`, `*.pyc`, `.git`) —
  [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160).
- The engine-native update *implementation* — the reproducible old/new render
  plumbing, the merge engine, the `--dry-run` and `--degraded` flags —
  [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161).
- The exact rejection wording for a pre-cutover `--engine-preview` project and
  any migration helper, and the retention specifics of the direct-Copier
  update route — [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162).
- The concrete cutover version number (`create-forge 0.4.0`), the supported
  OS / Python / install-mode matrix, the support and deprecation windows, and
  the cross-repository acceptance matrix — decided by CF-16.03
  ([ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md),
  canonical [engine-default cutover acceptance contract](engine-cutover-acceptance.md)).
- The generation-metadata document's schema, the `EngineErrorCode` values, the
  rename-record field names, and the reproducibility guarantee — all
  `forge-template`'s (FT-15.02, FT-17.01, FT-17.04). This contract adds no
  `forge-template` change (**CF-ROADMAP-01-EX-01**), no archetype, and no
  remote registry or plugin mechanism.

## Executable examples

Until the cutover ships, the contract is guarded rather than characterised:

- [`tests/test_engine_lifecycle_contract.py`](../tests/test_engine_lifecycle_contract.py)
  derives what it can from the live pre-cutover CLI — `update`'s parameter set
  is still `project` / `--ref` / `--dry-run`, `runner.update` still requires
  `.copier-answers.yml`, the engine `new` path still writes no `.git` and no
  `.forge/generation.json` — and carries tripwires that fail deliberately when
  [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) /
  [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) /
  [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) land, so the
  implementation cannot ship without bringing this document back into step. It
  also asserts
  [ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md) names
  its `CF-ROADMAP-01-AC-03` and `CF-ROADMAP-01-AC-05` obligations literally.
- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s
  link-audit guard keeps this document reachable from `CLAUDE.md`,
  `CONTRIBUTING.md` and [`docs/cli-conventions.md`](cli-conventions.md).

When the cutover implements a rule above, move it from this contract's
"decided" voice into the "in force" voice of
[`docs/filesystem-generation.md`](filesystem-generation.md) (the `new`
lifecycle) or [`docs/cli-conventions.md`](cli-conventions.md) (the `update`
surface), and add its characterization test, in the same pull request.
