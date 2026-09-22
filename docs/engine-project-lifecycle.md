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

**This contract is not the cutover, but every rule it decided is now
shipped.** CF-18.01 ([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md))
made the engine path the default `new` route (no flag needed).
[CF-18.03](https://github.com/Sandsy09/create-forge/issues/160)
([ADR 0045](adr/0045-engine-generation-lifecycle-and-staging-exclusions.md))
implemented rules 1-5 below — the `new` finalisation lifecycle and
the committed generation-metadata file — so the default path writes
`.git`, installs hooks when selected, and commits `.forge/generation.json`.
[CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
([ADR 0046](adr/0046-engine-native-update-application.md)) has since
implemented rules 6-23 — `create-forge update` now routes by file, runs a
Git-backed three-way merge with `git merge-file`, prints a genuine per-target
`--dry-run` list, and supports an opt-in `--degraded` two-way fallback.
[`docs/filesystem-generation.md`](filesystem-generation.md) and
[`docs/cli-conventions.md`](cli-conventions.md) are authoritative for that
shipped behaviour; the rules stay below too, as the decision record.

The two reserved `forge-template` `EngineErrorCode` values
(`invalid-generation-metadata`, `unsupported-generation-metadata`) are **not
shipped** at this contract's acceptance — FT-17.01 adds them. Nothing here
assumes they exist yet; the client-side "metadata file missing or unreadable"
path (§ Exit statuses) is `create-forge`'s own and stays distinct from them.

## The engine `new` finalisation lifecycle

**Shipped by [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160)
([ADR 0045](adr/0045-engine-generation-lifecycle-and-staging-exclusions.md));
[`docs/filesystem-generation.md`](filesystem-generation.md) is authoritative
for this behaviour, in force.** Rules 1-4 below record the decision as
implemented, by `create_forge.lifecycle`.

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

Rule 5's write is **shipped by CF-18.03** (in force in
[`docs/filesystem-generation.md`](filesystem-generation.md)); rule 6's
rewrite-on-update is **shipped by CF-18.04**
([ADR 0046](adr/0046-engine-native-update-application.md)).

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

**Rule 7 shipped by [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
([ADR 0046](adr/0046-engine-native-update-application.md)), by
`create_forge.update.route_for`; rule 8 shipped by
[CF-18.05](https://github.com/Sandsy09/create-forge/issues/162)
([ADR 0047](adr/0047-legacy-copier-retention-and-preview-transition.md)).**

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
   metadata, so it is byte-for-byte indistinguishable from any directory
   create-forge never touched (ADR 0047 rule 1). `update`'s single "neither
   file" diagnostic therefore names all three possible causes — never
   created by create-forge, the provenance file was deleted, or created by
   the removed development-only `--engine-preview` flag, which never
   supported updates — and points at regeneration with `create-forge new`.
   No metadata is fabricated and no answers are invented, and no migration
   helper is offered: ADR 0047 rule 2 records why one was considered and
   rejected.

## Engine-native update

**Shipped by [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
([ADR 0046](adr/0046-engine-native-update-application.md)).** `create_forge.pipeline`
orchestrates rules 9-15 (`prepare_update`); `create_forge.update` applies the
result (`apply_renames`, `apply_plan`). `forge_template.plan_update` performs
the classification itself (CF-ROADMAP-01-EX-01) -- `create-forge` never
re-implements it.

9. **Three file sets, provider-supplied old and new.** An engine-native
   update diffs, keyed by target:

   | Set | Source |
   | --- | --- |
   | **old** | `render_project(recorded spec)` on the recorded `forge-template` release -- reused from the freshly-computed *new* render with no second render or provisioning at all when the recorded and installed provider versions already match (ADR 0046 decision 3), otherwise provisioned into an isolated environment (ADR 0044) |
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

11. **Renames are applied to the working tree before diffing -- on a real run
    only.** When `.forge/generation.json`'s recorded component versions and
    the current ones straddle an owner-declared `{from, to, since}` rename
    record, the client applies each move to the working tree first, so a
    user's local edits travel with the moved path instead of being stranded
    ([`generation-provenance.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md);
    the catalogue declares none today). Under `--dry-run` the move is
    **simulated, not applied**: nothing is moved or staged, and the preview
    reads a renamed target's working bytes from its still-in-place old path
    instead, so it classifies exactly as a real run would
    ([create-forge#209](https://github.com/Sandsy09/create-forge/issues/209)).

12. **Per-target three-way merge with inline conflict markers.** For each
    target `create-forge` computes the classification
    `forge-template` fixes — `unchanged`, `added`, `removed`, `changed`,
    `renamed` — and merges old / new / working-tree by path, via `git
    merge-file -p` (ADR 0046 decision 4) rather than a bespoke merge
    algorithm. Where a template change and a local edit touch the same
    region, the merged file carries inline `<<<<<<<` / `=======` / `>>>>>>>`
    markers. A binary or otherwise non-mergeable `changed` target is decided
    by pristine-ness alone instead: replaced outright if pristine, left
    completely untouched and reported for manual review otherwise (ADR 0046
    decision 4) — never spliced with text markers. The result is left
    **staged but uncommitted**; the user reviews it with `git diff`, resolves
    any markers, and commits — the same workflow the direct-Copier route
    already documents.

13. **`removed`: delete only if pristine.** A target present in *old* and
    absent from *new* is deleted from the working tree only if its bytes still
    match *old*'s recorded digest. If it was locally modified, it is left in
    place with a warning that the template no longer manages it; the user
    decides.

14. **`skip-if-exists` targets are never touched on update.** A target whose
    `output` entry records `regeneration: "skip-if-exists"` (the `changelog`
    capability's `CHANGELOG.md`, so far the one shipped example) is never
    written, merged, or deleted during an update. `create-forge` notes it in
    the summary and moves on — "the engine records the disposition, the
    client applies the skip".

15. **A repeated no-op update changes nothing visible.** When the recorded and
    effective specs are equal and the installed release has not moved, every
    target classifies `unchanged`; `create-forge` detects this before touching
    the working tree, rewrites `.forge/generation.json` to byte-identical
    content (an empty `git diff`), and reports that nothing changed.

## `update --dry-run`

**Shipped by [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
([ADR 0046](adr/0046-engine-native-update-application.md)).** The effective
spec for an update is always the recorded spec verbatim (decision 6);
`update` gains no selection flags, and `--ref` — the Copier route's own
target-version flag — is rejected outright on the engine route, exit `1`,
naming `--legacy` as where it applies.

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

**Shipped by [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
([ADR 0046](adr/0046-engine-native-update-application.md)).** Write order is
merge, then `uv.lock`, then `.forge/generation.json` last, then one `git add
-A` covering all three (decisions 9-10) — a `uv.lock` refresh warns and keeps
the project on failure, rather than aborting an otherwise-good update.

18. **The clean-tree precondition is the rollback, and the guidance reads the
    real Git state.** *Amended by
    [CF-22.02](https://github.com/Sandsy09/create-forge/issues/194)
    ([ADR 0053](adr/0053-recover-updates-from-the-actual-git-state.md)); the
    original `git restore . && git clean -fd` is retired.* Because an
    engine-native update starts from a clean Git working tree, abandoning it is
    a Git operation back to `HEAD`. But the update **does** leave staged state
    behind — `git mv` stages a rename immediately, and a completed update ends
    in `git add -A` — and `git restore .` restores the working tree from the
    *index*, so it recovers neither. After a failure or cancellation
    `create-forge` therefore inspects the repository (read-only) and prints
    guidance for what it finds:

    | Found | Printed |
    | --- | --- |
    | nothing differs from `HEAD` | `No project files were changed; nothing to recover.` — no command |
    | changes exist and `HEAD` exists | `git -C <root> restore --source=HEAD --staged --worktree .` — correct for an unstaged, staged, partly-staged or post-`git mv` state; and, **only if untracked files exist**, `git -C <root> clean -nd` (preview) then `git -C <root> clean -fd` |
    | no commit to restore from | manual guidance and **no command** |
    | Git cannot be consulted | the same restore and review commands, unanchored, with a note to run them from the repository root |

    The text states that this returns the *whole repository* to its last commit
    and discards any uncommitted work made since. Untracked files are always
    previewed before deletion, and ignored files are never candidates (no
    `-x`). `create-forge` does **not** run any of it — the choice stays the
    user's. **Nothing is printed until the clean-tree precondition (§ 10) has
    passed:** before it, whatever is dirty is the user's own work, and no
    command that discards a working tree is theirs to run.

19. **`.forge/generation.json` is written last.** The refreshed metadata file
    is written only after the merge has fully succeeded. A failed or cancelled
    update therefore never leaves a half-written or inconsistent metadata
    file — the recorded spec still describes the last good state
    (CF-ROADMAP-01-AC-05).

20. **Exit codes.** A cancelled update exits `130`; a merge, render, or
    provisioning failure exits `1`. Both print the recovery guidance of § 18
    once the update has started. See § Exit statuses.

## Unavailable recorded release

**Shipped by [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
([ADR 0046](adr/0046-engine-native-update-application.md)).** Provisioning
the recorded release reuses the `--engine-source` machinery (ADR 0044); its
failure becomes `pipeline.UnavailableRecordedReleaseError`, carrying the
recorded version for the report below.

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
    unless `--degraded` is passed explicitly. `update.degraded_plan`
    (ADR 0046 decision 8) decides "pristine" from the recorded per-target
    digest in `.forge/generation.json` rather than a reproduced render, since
    none exists on this path — a pristine target is replaced outright, and
    everything else, including every genuinely locally-modified file, is left
    completely alone for manual review. When taken, the refreshed
    `.forge/generation.json` records
    `"reproduction": {"mode": "degraded", "reason": …}` so the next update
    knows the merge base was lost.

## `_message_after_update`

**Shipped by [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
([ADR 0046](adr/0046-engine-native-update-application.md)).**

23. **One client-owned post-update message, both routes.** `create-forge`
    owns the post-update next-steps text — the `_message_after_update` parity
    row is CF-16.02's, "client update dispatch and messaging". Both routes
    keep today's shape: `Updated. Review the diff before committing —
    conflicts are marked inline.` The engine route additionally reports a
    one-line count of clean versus conflicted targets. A no-op update
    (§ 15) reports that nothing changed instead.

## Update target containment

**Shipped by [CF-22.01](https://github.com/Sandsy09/create-forge/issues/193)
([ADR 0052](adr/0052-contain-every-client-filesystem-target.md)).** Every
string an engine-native update turns into a path — plan targets, rename
endpoints, the metadata filename, and the `output[].target` strings recorded in
`.forge/generation.json` — goes through the one shared boundary. The accepted
spelling, the refused names, symlink and junction containment, and the threat
model are defined once, for `new` and `update` alike, in
[filesystem-generation.md § Target safety](filesystem-generation.md#target-safety).

24. **The whole update is validated before its first mutation.** Before
    `create-forge` renames, writes, or deletes anything, it validates every
    plan target — including `skip-if-exists` and `unchanged` entries, which
    are never written but are still provider-supplied — both endpoints of
    every rename, and the metadata filename; the degraded path validates every
    new-render target and every recorded target. One unacceptable target
    anywhere refuses the whole update, so an invalid *late* target cannot leave
    a partial mutation behind. On the normal path the recorded document is not
    validated on its own: every recorded target the plan acts on appears as a
    plan target.

25. **Each filesystem operation revalidates its own target.** A read, write,
    delete, rename, or metadata refresh resolves its target again immediately
    before it happens. This narrows the window for a concurrent change to the
    working tree; it does not close it, and no race-safety guarantee is made.

26. **`--dry-run` reads nothing outside the project.** Validation runs before
    the first read, so a tampered recorded target is refused rather than opened
    — the dry run's "writes nothing" (§ 16) has a read-side counterpart.

27. **A refused target is exit `1`, sanitised.** The diagnostic names the
    target and the rule it broke, never a filesystem path or raw subprocess
    output, and reuses the existing exit-`1` row. Existing local-edit
    preservation, conflict handling, and the lock and provenance lifecycle are
    unchanged. The printed recovery hint is unchanged too; making it accurate
    for the project's actual Git state is
    [CF-22.02](https://github.com/Sandsy09/create-forge/issues/194)'s subject.

## Exit statuses

The [`docs/cli-conventions.md`](cli-conventions.md) exit-status table stays
authoritative and **unchanged**. Engine-native update failures map onto its
existing rows:

| Condition | Status |
| --- | --- |
| dirty Git working tree; non-Git project; a merge or render failure; `.forge/generation.json` missing when routing chose the engine, or unreadable JSON; neither route file present; a target refused by the containment boundary (§ 24) | `1` |
| the recorded `forge-template` release is incompatible with this CLI, or is unavailable and the degraded path was declined | `3` — the "required generator missing or unusable" class [ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md) already widened `3` to; not a new code |
| the user cancels a prompt or interrupts the merge | `130` |

No new exit code is introduced. The client-side "metadata file missing or
unreadable" case is `create-forge`'s own exit-`1` path and does not use — or
depend on the existence of — `forge-template`'s reserved
`invalid-generation-metadata` code.

## What this contract does not decide

- ~~The `_exclude` staging filter (`copier.yml`, `*.pyc`, `.git`)~~ — decided
  by CF-18.03 ([ADR 0045](adr/0045-engine-generation-lifecycle-and-staging-exclusions.md)):
  `staging.write_files` refuses the denylist; `copier.yml` itself is not
  applicable (see `docs/filesystem-generation.md`'s Target safety section).
- ~~The engine-native update *implementation* — the reproducible old/new
  render plumbing, the merge engine, the `--dry-run` and `--degraded`
  flags~~ — decided by CF-18.04
  ([ADR 0046](adr/0046-engine-native-update-application.md)): a
  version-match short-circuit reproduces the old render, `git merge-file -p`
  performs the merge, and `--degraded` decides pristine-ness from the
  recorded per-target digest.
- ~~The exact rejection wording for a pre-cutover `--engine-preview` project
  and any migration helper, and the retention specifics of the direct-Copier
  update route~~ — decided by CF-18.05
  ([ADR 0047](adr/0047-legacy-copier-retention-and-preview-transition.md)):
  one diagnostic names all three "neither file" causes, no migration helper is
  offered, and the direct-Copier route stays reachable independent of engine
  health.
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

Every rule this contract decided — rules 1-5 (`new` finalisation) and rules
6-23 (engine-native `update`) — is now shipped and characterised:

- [`tests/test_engine_lifecycle_contract.py`](../tests/test_engine_lifecycle_contract.py)
  derives the `new` finalisation lifecycle and the committed generation
  metadata from the live, shipped CLI (CF-18.03) — `pipeline.finalise_files`
  calls `lifecycle.finalise_project`, `lifecycle.py` runs `git init
  --initial-branch=main` and installs hooks, `engine.generation_metadata_target()`
  names the committed path — and derives the engine-native `update` route
  (CF-18.04): the full `--legacy`/`--degraded` parameter set,
  `cli.update_project` dispatching to `pipeline.prepare_update`/
  `update.apply_plan`, and the `git merge-file` merge mechanism. No
  CF-EPIC-18 tripwire remains in this file. It also asserts
  [ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md) names
  its `CF-ROADMAP-01-AC-03` and `CF-ROADMAP-01-AC-05` obligations literally.
- [`tests/test_lifecycle.py`](../tests/test_lifecycle.py) and
  [`tests/test_e2e_engine_generation.py`](../tests/test_e2e_engine_generation.py)
  characterise rules 1-5 directly — see
  [`docs/filesystem-generation.md`](filesystem-generation.md)'s own
  Executable examples for the full list.
- [`tests/test_update_routing.py`](../tests/test_update_routing.py)
  characterises rule 7's routing table and `read_recorded`'s lenient parsing.
- [`tests/test_update_engine.py`](../tests/test_update_engine.py)
  characterises rules 9-22 with real `git` (no mocked subprocess): the
  clean-tree precondition, rename application, every classification's
  application (including a synthetic `renamed` plan, since the shipped
  catalogue declares none), the real `git merge-file` merge and its conflict
  markers, the degraded fallback, and the version-match short-circuit against
  the real installed engine. Its two `@pytest.mark.e2e` cases run the real
  console script end to end (`new` then `update`) and provision the
  `../forge-template` sibling checkout as a stand-in recorded release to
  exercise the provisioning branch for real.
- `tests/test_cli.py`'s engine-native `update` section characterises the
  CLI orchestration: success/no-op/conflict reporting, the dry-run list, the
  relock warning, and the exit-status mapping for a dirty tree, `Ctrl-C`, and
  a declined or accepted degraded fallback. Its own `-k legacy`-selectable
  section (CF-18.05, ADR 0047) characterises rule 8's retention specifics:
  source validation on `new --legacy --template-url`, `_src_path`
  re-validation surviving the CLI's file-based routing, and the Copier route
  staying reachable when the installed engine cannot be imported.
- [`tests/test_update_routing.py`](../tests/test_update_routing.py)'s own
  `-k preview`-selectable tests (CF-18.05) characterise rule 8's rejection
  message and its no-fabrication guarantee.
- [`tests/test_e2e_installed_cutover.py`](../tests/test_e2e_installed_cutover.py)
  (CF-18.05) proves `create-forge[legacy]` resolves `copier`, `new --legacy`
  and `update` against a real local tagged Copier template preserve local
  edits and reach the newer tag, `--legacy` without the extra exits `3`, and
  a preview-era project is rejected — all through the installed console.
- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s
  link-audit guard keeps this document reachable from `CLAUDE.md`,
  `CONTRIBUTING.md` and [`docs/cli-conventions.md`](cli-conventions.md).

When the cutover implements a rule above, move it from this contract's
"decided" voice into the "in force" voice of
[`docs/filesystem-generation.md`](filesystem-generation.md) (the `new`
lifecycle) or [`docs/cli-conventions.md`](cli-conventions.md) (the `update`
surface), and add its characterization test, in the same pull request.
