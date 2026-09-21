# 52. Contain every client filesystem target behind one shared boundary

## Status

Accepted

## Context

[Issue #193 / CF-22.01](https://github.com/Sandsy09/create-forge/issues/193)
is the first child of
[CF-EPIC-22](https://github.com/Sandsy09/create-forge/issues/188), opened from
the 21 September 2026 engineering review. `create-forge` owns the destination
filesystem; `forge-template` returns strings.

The `new` path already treats those strings as untrusted:
`staging._safe_relative_path` refuses absolute, drive-qualified and `..`
targets, the `_exclude` names (ADR 0045) and anything that resolves outside the
staging root. The `update` path (ADR 0041, ADR 0046) did not. `update.py` joined
each of these to the project root with no check:

- provider-classified plan targets (`_apply_one`, `_merge_changed`);
- owner-declared rename endpoints (`apply_renames`, which also passed them to
  `git mv` as bare arguments);
- the engine-supplied metadata filename (`route_for`, `read_recorded`, and the
  refresh write in `cli.py`);
- the `output[].target` strings read back out of the project's own
  `.forge/generation.json` (`degraded_plan`) -- an ordinary committed file that
  a user or a repository can edit, which makes them the least trusted strings in
  an update.

`--dry-run` gated only the writes and deletes, never the reads above them, so a
tampered recorded target was read outside the project even when nothing was
supposed to change. This was reproduced at the function level against the
pre-change module: with a recorded digest equal to the digest of a file outside
the project, `degraded_plan` read that file under `dry_run=True` and deleted it
under `dry_run=False`. The trigger is an edited `.forge/generation.json`, so it
needs write access to a committed file the user then runs `update` against; this
record makes no claim about exploitation beyond that reproduction.

The staging resolver could not simply be reused. It is private to `staging.py`,
reports in generation vocabulary ("outside the staging directory"), and calls
`Path.resolve()` on a fresh directory, where a symlink or junction never
appears. An update runs against a long-lived working tree a user has edited.

## Decision

1. **One engine-free module owns the boundary.** `src/create_forge/paths.py`
   provides `relative_parts` (the accepted spelling, pure), `is_excluded` (the
   `_exclude` names), and `ProjectBoundary` (containment against a resolved
   root). It imports no `forge_template` -- not even under `TYPE_CHECKING` -- and
   is added to `tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard.
   `staging.py` and `update.py` both call it, so the two routes cannot disagree,
   and there is one place that states the threat model. `staging.py` keeps its
   own `StagingError` messages; `update.py` phrases a rejection as an
   `UpdateError`.

2. **The accepted spelling is a relative, forward-slash POSIX path with no dot
   components (`src/pkg/module.py`), and it is enforced identically on every
   host.** Rejected: empty or root-only, absolute, drive-qualified or
   drive-relative, UNC, any backslash, a `:` anywhere in a component (which also
   closes NTFS alternate data streams), `.`/`..`/empty components, control
   characters including NUL, Windows-reserved device names with or without an
   extension (`aux.py`), and a component ending in a dot or space. A target is
   not refused only where it happens to misbehave: a project updated on Linux
   and on Windows sees the same answer.

3. **The update path refuses the same names the `new` path does.** A `.git`
   segment anywhere, plus Copier's hygiene patterns. The `.git` refusal is the
   load-bearing one: the repository already exists, so a written
   `.git/hooks/pre-commit` would run on the user's next commit. The denylist
   moves from `staging.py` into `paths.py` so both routes share it.

4. **Containment is the fully-resolved location being a strict descendant of the
   resolved root.** The validated parts are joined to the real root and resolved,
   so an escaping final symlink, an escaping symlinked parent and a Windows
   junction or reparse-point escape are one rule, and a leaf that does not yet
   exist is contained by its resolved existing prefix. A link that resolves back
   *inside* the project is left working: a user's own internal symlink is a
   legitimate local edit, and refusing it would break a project the update
   previously handled. `ProjectBoundary.resolve` returns the *lexical* location
   under the resolved root rather than the fully-resolved one, so an internal
   symlink leaf is operated on as itself -- removing it removes the link, not its
   target -- exactly as before.

5. **Preflight the complete update, then revalidate at use.**
   `update.preflight_update` validates the metadata filename, every plan or
   new-render target (including `skip-if-exists` and `unchanged` entries, which
   are never written but are still provider-supplied), both endpoints of every
   rename, and every recorded target, before `cli.py` calls the first mutating
   function. `apply_renames`, `apply_plan` and `degraded_plan` also validate
   their own whole input before their first write, and each filesystem
   operation resolves its target again immediately beforehand. An invalid late
   target therefore leaves no partial mutation, and `--dry-run` reads nothing
   outside the project. On the normal path the recorded document is not
   validated separately: every recorded target the plan acts on already appears
   as a plan target.

6. **No race-safety is claimed.** Validation and use are separate system calls.
   A process that can mutate the project tree concurrently can replace a
   component between them; revalidating at use narrows that window and does not
   close it. The boundary defends against a malformed, hostile or tampered
   *target string*. It is not a defence against a party who already has write
   access to the working tree, and no supported-concurrency guarantee is made.

7. **Existing behaviour and exit codes are preserved.** A rejection is an
   `UpdateError`, already exit `1`; the diagnostic names the target and the rule
   it broke and never a filesystem path or raw subprocess output. `git mv` gains
   a `--` separator so a target beginning with `-` is a path, not an option.
   Merge, conflict handling, the lock and provenance lifecycle, and the recovery
   hint are untouched.

8. **The recovery hint stays with CF-22.02.** A containment rejection prints
   today's `ROLLBACK_HINT` exactly as malformed metadata already does. Making
   the hint accurate for the real Git state is
   [CF-22.02 (#194)](https://github.com/Sandsy09/create-forge/issues/194)'s
   subject, and doing it there in one pass avoids two issues editing the same
   message.

## Consequences

- **The `new` path inherits the stricter spelling.** Reserved device names,
  trailing dots and spaces, and a `:` are now refused when generating, not only
  when updating. Such a target could not be written on Windows in the first
  place. Rendering every archetype alone and with each single capability
  against `forge-template 0.6.0` (37 renders, 35 distinct targets) produced no
  refused target, and the unchanged generation and installed suites cover the
  full compositions; a provider that begins emitting such a target would now be
  refused on `new` too, which is the intent.
- **A pre-existing project whose recorded metadata names one of these targets
  will refuse to update.** Such a document could only have been produced by a
  target the `new` path now also refuses; the diagnostic names the target so the
  user can repair or regenerate the recorded file.
- **`paths.py` is a new module** in the architecture table, `CLAUDE.md` and the
  engine-boundary guard. It touches no engine and no Copier API, so invariant 4
  is unchanged.
- **The canonical contracts move with it.**
  [filesystem-generation.md](../filesystem-generation.md)'s "Target safety"
  section now describes one boundary serving both routes, and
  [engine-project-lifecycle.md](../engine-project-lifecycle.md) states the
  preflight, revalidation and dry-run rules.
- **Evidence is fast-suite, on Linux and Windows.** `tests/test_update_containment.py`
  builds real repositories and real links against an outside sentinel file and
  runs in the CI `test` matrix and the `windows` job; a host that will not
  create a symlink skips those cases and runs the junction ones instead.
  Installed-wheel evidence of the same behaviour is
  [CF-22.03 (#195)](https://github.com/Sandsy09/create-forge/issues/195)'s.
- **Out of scope, as the issue states:** provider-side filesystem mutation,
  catalogue duplication, and a general refactor of `update.py`. ADRs 0001-0051
  are untouched.
