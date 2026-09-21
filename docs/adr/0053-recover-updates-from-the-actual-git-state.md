# 53. Recover a failed update from the repository's actual Git state

## Status

Accepted. Supersedes, in part, [ADR 0041](0041-engine-project-lifecycle-and-update-dispatch.md)
rule 18 (the printed recovery command) and the recipe
[ADR 0048](0048-installed-cutover-acceptance-evidence.md) decision 4 exercised
for it.

## Context

[Issue #194 / CF-22.02](https://github.com/Sandsy09/create-forge/issues/194) is
the second child of
[CF-EPIC-22](https://github.com/Sandsy09/create-forge/issues/188). ADR 0041
rule 18 made the clean-tree precondition "the rollback": because an
engine-native update starts from a clean tree, recovery from any failure was
declared to be `git restore . && git clean -fd`, printed and never run. Published
`create-forge 0.4.0` prints exactly that on every failure or cancellation.

The premise was that "a failure mid-update never leaves anything staged". It
does, and the command is wrong or harmful in four ways:

1. **A staged update is not undone.** `stage_result` ends every update with
   `git add -A`. `git restore .` restores the working tree from the *index*, so
   with the result already staged it changes nothing, and `git clean -fd`
   removes only *untracked* files -- an added file is already tracked.
2. **An interrupted rename is not undone.** `apply_renames` runs `git mv`, which
   stages the rename before any other step. The same command fails for the same
   reason, from an interrupted update rather than a finished one.
3. **It is printed when nothing changed.** A malformed metadata document, a
   containment refusal
   ([ADR 0052](0052-contain-every-client-filesystem-target.md)) and any
   `--dry-run` failure all leave the tree exactly as it was, yet each printed a
   recovery command.
4. **It is printed when the update never started, and it destroys the user's
   work.** `require_clean_tree` refuses to begin when the tree has uncommitted
   changes -- the user's own -- and the handler then printed the same command,
   telling that person to discard them. The existing
   `test_engine_update_dirty_tree_exits_1_with_the_rollback_hint` asserted this.
   Of the four, this is the one that loses data.

These are reproduced against real repositories in
`tests/test_update_recovery.py`, which drives the update's real functions to each
state and shows the previous command leaving every staged state dirty.

## Decision

1. **Read the repository's state when a failure happens, and print guidance for
   it.** `update.recovery_guidance` runs three read-only Git queries (`rev-parse
   --show-toplevel`, `rev-parse --verify HEAD^{commit}`, `status --porcelain
   --untracked-files=normal`) and returns one of four states, each with its own
   text: **unchanged** ("No project files were changed; nothing to recover."),
   **restorable** (the restore command, plus an untracked review if any
   untracked files exist), **no HEAD** (manual guidance and no command, since
   there is nothing to restore from), and **unknown** (Git could not be
   consulted: the restore command and the untracked review, unanchored, with the
   user told to run them from the repository root). It never raises.

2. **Print recovery guidance only once the clean-tree precondition has
   passed.** `cli._run_engine_update` records that `require_clean_tree`
   succeeded and prints nothing before it. Before that point whatever is dirty
   is the user's own work, and inspecting Git alone cannot tell it from the
   update's: the tree would look restorable. This is the fix for defect 4, and
   it is why the guidance is gated rather than merely computed.

3. **One restore command: `git restore --source=HEAD --staged --worktree .`.**
   It names `HEAD` as the source and restores the index and the working tree, so
   it is correct for an unstaged, a staged, a partly-staged and a post-`git mv`
   state alike; in `restore`'s default no-overlay mode it also removes tracked
   paths absent from `HEAD`, which is what undoes a staged addition or the
   destination of a staged rename. The separate "worktree-only" form, which
   [the issue](https://github.com/Sandsy09/create-forge/issues/194) permits
   only when the index is unchanged, is not offered: with the index equal to
   `HEAD` it is the same command with a different source, so it would double the
   documented surface for no additional safety.

4. **Review before deleting.** When `git status` reports untracked files, the
   guidance prints `git clean -nd` (list them, delete nothing) before `git clean
   -fd`, and says to delete only if sure. There is no `-x`, so ignored files are
   never candidates. The two are separate lines, never chained.

5. **Anchor every command at the repository root.** Commands are printed as
   `git -C <root> ...`, so they are correct from any directory and any shell. A
   project that is a subdirectory of a larger repository is restored as a whole
   repository, and the text says so; that is correct because `require_clean_tree`
   runs a repository-wide `git status`, so the entire repository was already
   required to be clean.

6. **State the scope.** The text says the restore returns the whole repository to
   its last commit (`HEAD`) and discards any uncommitted work made since, so a
   user who has kept working after the update does not lose it by surprise. The
   guide additionally states the two assumptions -- a clean start and an unmoved
   `HEAD` -- and that a *committed* update is undone with `git revert`.

7. **Never execute recovery.** `create-forge` prints; it does not run. There is
   no automatic rollback, no `--rollback` flag and no backup subsystem.

8. **One source for the commands.** `update.RESTORE_COMMAND`,
   `CLEAN_PREVIEW_COMMAND` and `CLEAN_COMMAND` are the printed commands.
   `RecoveryGuidance.commands()` returns the argv the tests execute, so the
   guidance the CLI prints is the guidance that is proven. `ROLLBACK_HINT` is
   removed. `tests/recovery_recipes.py` repeats the strings for the installed
   suites and the guide's drift guard, with an equality test against the module.

9. **Exit codes and messages other than the hint are unchanged.** `1`, `130` and
   `3` are as before; the `EngineCompatibilityError` path still prints no
   guidance. The hint is the only output that changes.

## Consequences

- **Published `create-forge 0.4.0` still prints the old command.** Releases are
  immutable, so the fix ships with the next release. The user guide therefore
  documents the corrected procedure as plain Git steps -- correct on every
  version -- with an explicit note that 0.4.0 prints a command that does not undo
  a staged update; it says nothing about the unreleased build's output. The
  published `v0.4.0` release notes, which quote the old command, are corrected
  in place; that edits a notes body only, not the tag, wheel or sdist.
- **The state inspection adds Git calls to the failure path only.** It is
  bounded (30 s), read-only, decodes leniently so it does not depend on the
  console codepage, and falls back to the unknown-state text rather than failing.
- **The canonical contracts move with it:**
  [engine-project-lifecycle.md](../engine-project-lifecycle.md) rule 18 and its
  Rollback section, [cli-conventions.md](../cli-conventions.md),
  [engine-cutover-acceptance.md](../engine-cutover-acceptance.md), the README,
  and the user guide's `updates.md` and `migration.md`.
- **The dry-run exception is not fixed here.** `--dry-run` is documented to write
  nothing, but `apply_renames` runs before the dry-run check and takes no
  `dry_run` argument, so a plan containing a rename would `git mv` during a dry
  run. No shipped template declares a rename, so it is unreachable today. It is a
  separate defect with its own design question (a dry run must simulate the
  rename, because `apply_plan` reads the renamed path) and is tracked separately.
  Reading the state at failure time means the guidance would already be correct
  if it happened.
- **Installed-wheel evidence** of both recovery states and of the dirty-tree case
  is [CF-22.03 (#195)](https://github.com/Sandsy09/create-forge/issues/195)'s.
- **Out of scope:** automatic rollback, a snapshot or backup facility, and
  recovery of a stale `.git/index.lock`. ADRs 0001-0052 are untouched.
