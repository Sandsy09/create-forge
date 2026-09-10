# 41. Define engine project lifecycle and update dispatch

## Status

Accepted

## Context

[ADR 0040](0040-engine-default-selection-and-source-resolution.md) fixed the
post-cutover CLI *selection and source-resolution* surface — the engine as the
default `new` path, `--legacy` for direct Copier, `--engine-source` renders
that write no metadata — and deferred, by name, to
[CF-16.02 / #156](https://github.com/Sandsy09/create-forge/issues/156): the
generation-metadata filename and location, the engine-native update dispatch,
merge, conflict, dry-run, cancellation and rollback policy, the
`_tasks`-equivalent Git and hook lifecycle for the engine `new` path, the
`_message_after_update` parity row, and old preview-project handling.

The provider side is fixed. `forge-template`'s
[generation-provenance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md)
(FT-15.02, forge-template ADR 0059) defines the seven-field metadata document,
the three-file-set update model (**old** = `render_project(recorded spec)` on
the provisioned recorded release, **new** = `render_project(effective spec)`
on the current release, **working tree** = the client reads disk), the closed
classification vocabulary `unchanged / added / removed / changed / renamed`,
the per-target `regeneration: "replace" | "skip-if-exists"` disposition, the
owner-declared `{from, to, since}` rename records the client applies **before
diffing**, the fail-closed-then-opt-in-degraded rule for an unavailable
recorded release, and `reproduction.mode = "degraded"`. It assigns the client
"the working-tree diff and merge, on-disk conflict resolution, Git, hook
execution, and all presentation", and it leaves the client **everything about
how**: the filename, whether Git is used, the merge algorithm, conflict
markers, the dry-run output, the rollback mechanism, and the messages.
[engine-default-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/engine-default-parity.md)
assigns the `_tasks` row (`git init` / `add` / `commit`, lockfile commit,
`pre-commit install`) and the `_message_after_update` row to CF-16.02, both
`disposition: client` — "the engine spawns no process".
[cutover-compatibility-and-acceptance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)
guarantees `copier update` keeps working for every existing direct-Copier
project, with no `_migrations` block.

Two provider facts bound the answers. The two reserved `EngineErrorCode`
values (`invalid-generation-metadata`, `unsupported-generation-metadata`) are
not shipped at this contract's acceptance — FT-17.01 adds them — so nothing
here may assume they exist. And forge-template ADR 0059 decision 1 commits
FT-17.01 to publish "one documented default target" for the metadata file
while its living contract calls the filename "a client decision"; this
decision resolves that by fixing the filename and asking FT-17.01 to adopt it.

This is a decision issue. It records the contract in
[`docs/engine-project-lifecycle.md`](../engine-project-lifecycle.md) and
updates the living contracts it touches. It changes no runtime code, moves no
dependency, bumps no version, and requires no `forge-template` change beyond
the filename-adoption ask. Every implementing step is an already-filed
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153) child:
[CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) (engine `new`
finalisation, Git, hooks),
[CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) (engine-native
update), [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162)
(legacy and preview-project transition).

Its review obligations are **CF-ROADMAP-01-AC-03** (client ownership of
staging, VCS/hooks, update dispatch and cleanup is explicit and testable —
shared with CF-18.03 and CF-18.04) and **CF-ROADMAP-01-AC-05** (existing
Copier projects keep a documented update route and the rollback plan does not
corrupt their stored answers — shared with CF-18.05).

## Decision

1. **Route `update` by file, with `--legacy` forcing the Copier route.**
   `create-forge update <project>` selects the engine-native route when the
   project contains `.forge/generation.json`, the direct-Copier route
   (`runner.update`, unchanged) when it contains only `.copier-answers.yml`,
   and the engine-native route when it contains both — unless `update
   --legacy` is given, which forces the Copier route in every case. Neither
   file present is an exit-`1` error naming both routes. The engine-native
   route never reads or rewrites `.copier-answers.yml`.

2. **Reject a pre-cutover `--engine-preview` project with guidance.** Such a
   project has neither file. `update` exits `1` explaining it was made by the
   removed development-only flag, which never supported updates, and pointing
   to regeneration with `create-forge new`. No metadata is fabricated and no
   answers invented. [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162)
   owns the exact wording and any migration helper.

3. **Persist the generation metadata as a committed `.forge/generation.json`.**
   `create-forge` serialises `forge-template`'s generation-metadata document
   to JSON at `.forge/generation.json` in the project root and commits it to
   the project's own Git repository, exactly as a direct-Copier project
   commits `.copier-answers.yml` — so a collaborator or CI reproduces or
   updates from the same recorded spec. `create-forge` adds no field. The ADR
   asks FT-17.01 to adopt `.forge/generation.json` as the "one documented
   default target" forge-template ADR 0059 reserves, so the two repositories
   name one path.

4. **Rewrite `.forge/generation.json` on every successful update, last.**
   After a successful engine-native update the file is rewritten to the new
   effective spec, component versions, protocol integers, provider version,
   and output digests, and left staged-but-uncommitted with the merged files.
   It is written only after the merge fully succeeds (decision 9), so a failed
   or cancelled update never leaves it half-written. `reproduction.mode` is
   `"degraded"` only on the degraded path (decision 10).

5. **Run the engine `new` Git and hook lifecycle at the final path, after the
   rename.** The render stays staged and atomically renamed
   ([`docs/filesystem-generation.md`](../filesystem-generation.md)); only then,
   against the destination, does `create-forge` run `git init`, `git add -A`,
   and one initial `git commit` whose message matches the direct-Copier
   `_tasks` commit. `uv.lock` (already resolved in staging, ADR 0021) and
   `.forge/generation.json` are part of that commit. Running the lifecycle in
   staging would bake the staging path into `.git/hooks/` and any shims — the
   same reason the Copier path cannot be renamed after `_tasks`.

6. **Install hooks only when a `.pre-commit-config.yaml` was rendered.**
   `create-forge` runs `pre-commit install --install-hooks` only if the render
   produced that file — which, on the engine path, means the `pre-commit`
   capability was selected. The client checks for the rendered file it already
   holds; it inspects no component id.

7. **Keep the project and warn when a lifecycle step fails.** A failure of
   `git init`, the initial commit, or `pre-commit install` after a good render
   leaves the project in place, prints the one manual command that finishes
   the step, and still exits `0`. A render, lock, or rename failure still
   cleans up and exits `1`, unchanged.

8. **Perform the engine-native update as a Git-backed three-way merge from a
   clean tree.** The update refuses to start unless the Git working tree is
   clean (as `copier update` does). It applies any straddling `{from, to,
   since}` rename record to the working tree first, then merges old / new /
   working-tree per target, writing inline `<<<<<<<` / `=======` / `>>>>>>>`
   markers where a template change and a local edit collide, and leaves the
   result staged for the user to review with `git diff` and commit. A
   `removed` target is deleted only if its bytes still match old's recorded
   digest; a locally-modified one is kept with a warning. A
   `regeneration: "skip-if-exists"` target is never written, merged, or
   deleted — noted, not acted on. A no-op update rewrites byte-identical
   metadata and reports that nothing changed.

9. **Make the clean-tree precondition the rollback, and print — never run —
   the recovery command.** Recovery from any mid-merge failure, render
   failure, or `Ctrl-C` is `git restore . && git clean -fd`, which
   `create-forge` prints on failure and does not execute itself, because a
   tool running `git clean -fd` can delete untracked files the user wanted.
   `.forge/generation.json` written last (decision 4) is what keeps a failed
   update from corrupting the recorded spec.

10. **Fail closed on an unavailable recorded release, with an opt-in degraded
    update.** When the recorded `forge-template` release cannot be obtained,
    `create-forge` fails before any render or write with the four report
    facts. It may then proceed with a degraded two-way update (new render vs
    working tree, no old render) — never automatically: interactively `update`
    asks and explains the lost merge base; non-interactively it stays failed
    unless `--degraded` is passed. The degraded path records
    `reproduction.mode = "degraded"` with a reason.

11. **Give the engine route a real `--dry-run` preview; leave the Copier
    route's unchanged.** The engine-native `--dry-run` prints each affected
    target with its classification, marked clean or CONFLICT, `unchanged`
    summarised as a count, and writes nothing. The direct-Copier `--dry-run`
    stays the `pretend=True` validation preview it is today.

12. **Own the `_message_after_update` text on both routes.** Both keep today's
    `Updated. Review the diff before committing — conflicts are marked
    inline.`; the engine route adds a one-line clean/conflicted target count.
    This closes the parity row.

13. **Reuse the existing exit-status table unchanged.** Dirty tree, non-Git
    project, merge/render failure, missing-or-unreadable metadata, no route →
    `1`. Recorded engine incompatible, or unavailable with the degraded path
    declined → `3`, the "required generator missing or unusable" class
    [ADR 0040](0040-engine-default-selection-and-source-resolution.md) already
    widened `3` to. Cancellation → `130`. No new code. The client-side
    missing-or-unreadable-metadata path is `create-forge`'s own and does not
    use or depend on `forge-template`'s reserved
    `invalid-generation-metadata` code.

14. **Publish the contract as `docs/engine-project-lifecycle.md`.** A new
    canonical living document in the idiom of
    [`docs/engine-default-cli.md`](../engine-default-cli.md).
    [`docs/filesystem-generation.md`](../filesystem-generation.md) keeps the
    staging, atomic-rename and cleanup rules and gains a pointer to the
    lifecycle step that follows the rename;
    [`docs/cli-conventions.md`](../cli-conventions.md) gains a pointer section
    and its `## Update dry runs` section is revised; the exit-status **table**
    is untouched. No new issue is filed — every implementing step maps to an
    existing CF-EPIC-18 child.

## Consequences

- `docs/engine-project-lifecycle.md` is added and linked from `CLAUDE.md`,
  `CONTRIBUTING.md`, and `docs/cli-conventions.md`;
  `tests/test_engine_contract.py` gains a link-audit guard copying the
  existing ones.
- `tests/test_engine_lifecycle_contract.py` is added: derived assertions
  against the live pre-cutover CLI, plus tripwires that fail deliberately when
  CF-18.03 / CF-18.04 / CF-18.05 land — `update` still has only
  `project` / `--ref` / `--dry-run`, `runner.update` still requires
  `.copier-answers.yml`, the engine `new` path still produces no `.git` and no
  `.forge/generation.json`, `cli.py` still dispatches `update` only to
  `runner.update`. It also asserts this record names `CF-ROADMAP-01-AC-03` and
  `CF-ROADMAP-01-AC-05` literally.
- `docs/cli-conventions.md`, `docs/filesystem-generation.md`,
  `docs/engine-updates.md`, `docs/engine-default-cli.md`, and
  `docs/integration-contract.md` are updated to point at the new contract and
  to replace their "the engine path writes no `.git` / has no update contract"
  language with a reference to this decision. The
  `integration-contract.md` compatibility table is untouched — no range moves
  here.
- `forge-template` FT-17.01 inherits a concrete filename to adopt
  (`.forge/generation.json`) rather than choosing one that might diverge from
  the client's.
- `CF-16.02`'s three acceptance bullets and its two `CF-ROADMAP-01` review
  obligations are satisfied by the new ADR and contract; `CF-16.03` is
  unblocked.
- The lifecycle and update behaviour this contract describes is still unbuilt.
  This ADR performs no dependency move, no version bump, no CLI code change,
  no `forge-template` code change, and no release — CF-18.03 onward do that,
  and until they land the engine path stays behind `--engine-preview` and
  `create-forge update` handles only direct-Copier projects.
