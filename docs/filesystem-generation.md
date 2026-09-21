# Filesystem Generation

This is the living contributor contract for how `create-forge` turns a
successful render into a project on disk, and how it recovers from a failed
one. [ADR 0015](adr/0015-staged-filesystem-generation.md) established adjacent
staging; [ADR 0021](adr/0021-client-finalises-engine-lockfiles.md) adds the
client-owned lock finalisation this document keeps current.

## Status

`src/create_forge/staging.py` is the one module both generation paths share.
It is deliberately engine-free — it imports nothing from `forge_template`,
not even under `TYPE_CHECKING` — so it ships in the wheel and runs in the
fast test suite with no `engine` extra installed.
[`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s
`_SHIPPED_MODULES` guard enforces this the same way it enforces
`engine.py`'s import boundary.

## Ownership split

`forge-template` renders and validates entirely in memory: `render_project`
calls the public `validate_rendered_project` before returning, so a
`RenderedProject` `create-forge` receives has already passed the
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md).
`create-forge` does not call `validate_rendered_project` itself and must not
reimplement its checks. What `create-forge` owns is everything after that:
destination conflicts, where generation happens on disk, moving a completed
result into place, creating dynamic client-finalisation artefacts, cleaning up
a failed one, and the terminal messages for each.

## The two generation paths differ, deliberately

**The engine path is staged.** `pipeline.finalise_generation_request`
renders and validates fully in memory first (nothing on disk exists yet),
then calls `staging.staged(dst)`, which creates a temporary directory
**adjacent to `dst`** — inside `dst.parent`, via `tempfile.mkdtemp`, not the
system temp directory — writes every rendered file into it, runs
`uv lock --directory <staging-directory>`, and finalises with `Path.rename`.
The lock is outside `RenderedProject` and `GenerationPlan`: it is a dynamic
dependency-resolution result owned by the client, not reviewed engine content.
Same-volume placement is what makes the final rename an
atomic directory rename on both NTFS and POSIX; there is no cross-volume
copy fallback, so a cross-volume destination fails with a clear message
instead of silently losing the atomicity guarantee.

**The Copier path is cleaned up, not staged.** `forge-template`'s
`copier.yml` declares `_tasks` — `git init`, `uv sync --all-groups`,
`uv run pre-commit install --install-hooks` — that run *during* `run_copy`,
at whatever path `dst_path` names. `uv sync` bakes `dst`'s absolute path
into `.venv/pyvenv.cfg` and its console-script shims; `pre-commit install`
bakes it into `.git/hooks/pre-commit`. Renaming a completed Copier output
afterward would silently break all three, and Copier has no mechanism to
re-run `_tasks` at a new path after the fact. So `runner.scaffold` calls
`staging.discard_on_failure(dst)` around the real `run_copy` call instead: on
failure, it removes `dst` **only if this call created it** — a destination
that already existed before the command ran (an unusual `--path` pointed at
an existing empty directory) is left exactly as it was found.

Both paths share the same non-empty-destination check
(`staging.ensure_available`) and run it before any other side effect,
including before an engine compatibility check or import.

**`--engine-source` (ADR 0044) reaches the same staging through
`pipeline.finalise_files`, not `finalise_generation_request`.** The override
route runs its ProjectSpec build, validation, and render out of process
(`engine_source.py`/`_engine_worker.py`), so it never holds a real
`forge_template.RenderedProject` — only plain `(target, content)` byte pairs.
`finalise_generation_request` is now a one-line wrapper over
`pipeline.finalise_files(files, destination)`, the extracted staging/lock/
atomic-rename body both routes call; the default route just supplies
`request.rendered.files` mapped to that same pair shape. Staging placement,
target-safety checks, lock creation, atomic rename, and cleanup-on-failure are
therefore identical on every route this document describes — there is no
third finalisation behaviour to learn.

## Engine lock finalisation

`staging.create_uv_lock` executes the fixed command directly, without a shell,
after all reviewed files are present and before the staging context renames the
tree. `create-forge[engine]` includes `uv>=0.12,<0.13`; the default Copier path
does not gain another uv dependency or task.

A missing executable, process-launch error, or non-zero resolver status becomes
an actionable `StagingError`. Raw subprocess output is not exposed because
resolver diagnostics and package-index URLs can contain credentials. The
staging context removes the incomplete tree and leaves the destination
untouched. Engine output written into staging contains `uv.lock` and the
generation-metadata document (below); `.git`, `.venv`, and hooks are never
written in staging — the lifecycle below runs only after the rename.

## The generation-metadata document

`pipeline.finalise_files` accepts an optional `metadata_json: str | None`.
When the caller supplies one — `finalise_generation_request` always does, from
`RenderedProject.metadata.to_json()` — it is written into the staging tree at
`engine.generation_metadata_target()` (re-exported from
`forge_template.DEFAULT_GENERATION_METADATA_TARGET`, `.forge/generation.json`)
through the same `write_files` target-safety pass as every rendered file, and
before `create_uv_lock` runs. The re-export is a lazy function, not a
module-scope import (ADR 0045): an out-of-range engine that predates this
constant (published only at the `0.5.0` cutover) would otherwise turn a
version mismatch into a misleading "engine not installed" `ImportError`,
raised before `negotiate_protocol`'s own compatibility check ever runs; by
the time `finalise_files` calls it, a render has already succeeded through
every compatibility-gated function, so compatibility is already confirmed.
This keeps the atomic-rename guarantee whole:
there is no window where `dst` exists without its own provenance document, and
a metadata-write failure is an ordinary staging failure — cleans up, exits `1`
— not a special case. `finalise_generation_request` fails closed with a
`StagingError` *before any write* if `RenderedProject.metadata` is `None`: the
installed engine always returns one, so a `None` here is a provider-contract
violation, and a silently un-updatable project is worse than an explicit exit
`1`. `--engine-source` (ADR 0044 rule 29) calls `finalise_files` with no
`metadata_json` — it still writes no metadata document, since it never holds a
real `RenderedProject` to take one from.

## The `new` Git and hook lifecycle

A **`new` finalisation step runs after the atomic rename**, at the final
destination — `git init` + `git add -A` + one initial commit, then
`pre-commit install --install-hooks` only if the render produced a
`.pre-commit-config.yaml` — the engine analogue of the Copier path's
`_tasks`. It runs after the rename, not in staging, for the same
absolute-path reason the Copier path is cleaned-up rather than staged: `git
init` and `uv run --install-hooks` (which implicitly creates/syncs `.venv`
from the staged `uv.lock`) both bake `dst`'s absolute path into `.git/hooks/`
and `.venv/`.

`create_forge.lifecycle` owns this step — a new, engine-free module (ADR
0045), called from `pipeline.finalise_files` once the rename has succeeded.
It never raises: a `git init` failure skips every later step (nothing else
can succeed without a repository); a failed `git add` skips only the commit
(hook installation needs `.git/` but not a commit); every other failure is
independent. Each failure becomes one warning naming the exact manual command
that finishes the step; `cli.py` prints every warning it gets back and `new`
still exits `0` — the render is sound, and the convenience step is not worth
discarding it for (ADR 0041 rule 4). No warning ever includes raw subprocess
stdout or stderr, the same rule `create_uv_lock` and `engine_source.py`
already apply. `--engine-source` gets the identical lifecycle (minus the
metadata document, above) — `git init` is unrelated to update-eligibility, and
the success panel already says the project is not updatable.

One asymmetry worth knowing: a project with the `pre-commit` capability
selected ends generation with a populated `.venv` (created by `uv run
--install-hooks`); one without the capability does not.

This is CF-16.02's decision
([ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md),
canonical [engine project lifecycle contract](engine-project-lifecycle.md)),
built by [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160)
([ADR 0045](adr/0045-engine-generation-lifecycle-and-staging-exclusions.md));
the staging, atomic-rename and cleanup rules on this page are unchanged by it.

## Target safety

One client-owned boundary, `create_forge.paths`
([ADR 0052](adr/0052-contain-every-client-filesystem-target.md),
[CF-22.01](https://github.com/Sandsy09/create-forge/issues/193)), turns every
engine-supplied target *string* into a filesystem path. `RenderedFile.target`
and `UpdateTarget.target` are documented as project-relative, but that is not
assumed without checking: the safety boundary belongs to `create-forge`, the
same way destination-conflict and path-traversal checks always have. Two routes
use it — `staging.write_files` when generating, and `update.py` when applying
an engine-native update (see
[engine-project-lifecycle.md](engine-project-lifecycle.md)) — so they cannot
disagree about what a target may be.

### Accepted spelling

A target is a relative, forward-slash POSIX path with no dot components:
`src/pkg/module.py`. Everything below is rejected on **every** host, not only
where it would misbehave, so a target that works on Linux works on Windows:

| Rejected | Examples |
| --- | --- |
| empty or root-only | `""`, `"."`, `"/"`, `"//"` |
| absolute | `/etc/passwd`, `//server/share/x` |
| drive-qualified, drive-relative, or a `:` anywhere (which also covers NTFS alternate data streams) | `C:/x`, `C:x`, `a.txt:stream` |
| any backslash (a UNC path, `C:\...`, or a Windows separator) | `a\b`, `\\server\share\x` |
| `.`, `..` or empty components | `../x`, `a/../b`, `a//b`, `a/` |
| control characters, including NUL | a NUL or newline byte inside a name |
| Windows-reserved device names, with or without an extension | `aux.py`, `CON`, `COM1`, `nul.tar.gz` |
| a component ending in a dot or space | `a./b`, `a /b` |

### Refused names

Also refused, on both routes and with nothing written: a `.git` path segment
anywhere, `*.py[co]`, `__pycache__`, a `~`-prefixed name, and `.DS_Store`
(ADR 0045, [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160)).
The `.git` refusal is load-bearing, not merely hygienic: on `new` the lifecycle
above runs `git init` at `dst` after the rename, so a rendered
`.git/hooks/pre-commit` would survive re-initialisation and later execute as a
real hook; on `update` the repository already exists, so a written hook would
run on the user's next commit. `copier.yml` itself is not in this list: it is a
template-source file Copier had to avoid copying into its own output, and the
engine has no equivalent input to accidentally re-emit.

### Containment

The validated parts are joined to the project's resolved root and fully
resolved, and the result must be a strict descendant of that root. One rule
therefore covers an escaping **final symlink**, an escaping **symlinked
parent**, and a **Windows junction** or reparse-point escape, and a leaf that
does not exist yet is contained by its resolved existing prefix. A link that
resolves back *inside* the project is left working — a user's own internal
symlink is a legitimate local edit. `ProjectBoundary.resolve` returns the
lexical location under the resolved root, so an internal symlink leaf is
operated on as itself (removing it removes the link, not its target).

`staging.write_files` validates every `(target, content)` pair before writing
anything: one refused target aborts the whole call with nothing written by it.

### Threat model

This defends against a malformed, hostile or tampered *target string* — an
engine result, a rename record, or a `.forge/generation.json` a user or a
repository has edited. Validation and use are separate system calls, so a
process that can mutate the project tree concurrently could swap a component
between them. Callers revalidate immediately before each filesystem operation,
which narrows that window and does not close it: **no race-safety guarantee is
made**, and the boundary is not a defence against a party who already has write
access to the tree.

## Finalisation and cleanup

| Path | On success | On failure |
| --- | --- | --- |
| Copier (`runner.scaffold`) | `dst` contains the completed project, written directly by Copier. | `dst` is removed if this call created it; left untouched if it pre-existed. |
| Engine (`pipeline.finalise_generation_request`) | Rendered files, the generation-metadata document, and `uv.lock` are complete before the staging directory is renamed to `dst`; the Git/hook lifecycle then runs at `dst`. No intermediate state is ever visible there. | Write, lock, or rename failure removes the staging directory; `dst` is left exactly as it was found — created or not. A lifecycle failure *after* a successful rename keeps `dst` and warns instead — see above. |

Cleanup never raises over the exception that triggered it: a residual
directory that cannot be removed (e.g. a locked file) is reported as a
warning, and the original error still propagates. Read-only files are
handled — cleanup clears the read-only bit before retrying a removal — since
generated content is not assumed to be writable.

`--dry-run` short-circuits before staging or lock creation on either path: the
Copier path passes Copier's own `pretend=True`; the engine path lists the
rendered targets and returns. Neither path writes anything under `--dry-run`.

## Exit statuses

A rejected non-empty destination and a staging, lock, or finalisation failure both
exit `1`, in the same bucket as other scaffold/update failures — see the
[CLI conventions](cli-conventions.md#exit-statuses) exit-status table. They
are distinguished from `EngineCompatibilityError`'s exit `3` because they are
not a protocol/package incompatibility: the engine already ran successfully
by the time either can occur.

## Executable examples

- [`tests/test_staging.py`](../tests/test_staging.py) — destination conflict
  detection; target-safety refusals (absolute, drive-qualified, `..` targets,
  and the `_exclude` denylist: `.git` at any depth, `*.py[co]`,
  `__pycache__`, `~`-prefixed names, `.DS_Store`); staging directory
  placement (adjacent to `dst`, not the system temp directory); uv
  command/error translation; atomic finalisation; staging-tree cleanup on
  failure, including read-only files; `discard_on_failure` removing only a
  destination it created.
- [`tests/test_lifecycle.py`](../tests/test_lifecycle.py) (CF-18.03, ADR
  0045) — `finalise_project`'s step order and gating (hooks only when
  `.pre-commit-config.yaml` exists; a `git init` failure skips every later
  step; a failed `git add` skips only the commit); every failure mode
  reported as a warning naming the manual command, never raising and never
  echoing raw subprocess output.
- [`tests/test_pipeline.py`](../tests/test_pipeline.py) —
  `finalise_generation_request` against a real `RenderedProject`, command
  ordering before rename, write/lock failures leaving nothing behind, the
  metadata document landing in staging before the rename, `metadata is None`
  failing closed with nothing written, and the lifecycle running only after
  a successful rename with its warnings propagated to the caller.
- [`tests/test_cli.py`](../tests/test_cli.py) — the default engine `new` path
  (`test_new_rejects_a_non_empty_destination_before_the_engine`) against a
  non-empty destination exits before the engine is touched;
  `test_new_dry_run_lists_targets_and_writes_nothing` neither writes nor
  resolves; `test_new_reports_lock_failure_and_writes_nothing` exits `1` and
  writes nothing; `test_new_finalises_a_successful_render` asserts the
  committed metadata document lands on disk;
  `test_new_prints_a_lifecycle_warning_and_still_exits_0` proves a lifecycle
  warning is printed without turning into a non-zero exit; the
  characterized-failure cases assert no destination and no leftover staging
  directory.
- [`tests/test_data_science_pipeline.py`](../tests/test_data_science_pipeline.py)
  (CF-13.05) — the same guarantees for the multi-component Data Science
  composition: a full staged/locked/finalised project on disk, dry-run
  listing exactly the engine's own planned targets and writing nothing, and
  five failure modes (missing requirement, invalid option, incompatible
  engine, destination conflict, lock failure) each leaving no partial
  project and no staging sibling.
- [`tests/test_e2e_engine_generation.py`](../tests/test_e2e_engine_generation.py)
  (CF-18.03) — a real console-script `new` with `--capability pre-commit`
  proves the full lifecycle against a real `git`/`uv`: exactly one commit
  with the exact message, `uv.lock` and `.forge/generation.json` tracked in
  it, the committed metadata document's digests matching the files on disk,
  and `.git/hooks/pre-commit` installed; a real Git-identity-stripped
  subprocess proves a lifecycle failure keeps the project, prints the manual
  command, and still exits `0`; a pre-existing destination is left byte-for-
  byte untouched. `docs/engine-cutover-acceptance.md`'s finalisation row
  names the exact `-k` selectors these satisfy, including a dedicated
  `windows-latest` CI run.
- [`tests/test_e2e_installed_rollout.py`](../tests/test_e2e_installed_rollout.py)
  (CF-14.03, [ADR 0033](adr/0033-complete-rollout-regression-validation.md)) —
  the same guarantees through the *installed* `0.3.0` console script:
  `test_installed_non_empty_destination_is_preserved` on both paths,
  `test_installed_lock_failure_leaves_no_partial_project` (a real emptied-`PATH`
  `create_uv_lock` failure, not a fake), every `test_installed_failure_case_*`
  asserting no destination and no `.create-forge-*` staging sibling, and (since
  CF-18.03) `test_installed_engine_archetype_has_the_expected_shape` asserting
  the committed `.forge/generation.json` and a real `.git` directory.
  `tests/installed_client.py`'s shared `assert_output_matches_owned_plan`
  excludes `.git/` internals from its byte-for-byte comparison (their content
  is git's own bookkeeping, not part of the owned render) and expects
  `.forge/generation.json` alongside `uv.lock`; `tests/test_e2e_installed_data_science.py`
  (CF-14.02) reuses both.
- [`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py)
  — the adopted `validate_rendered_project` contract against the real pinned
  engine, proving what `finalise_generation_request` relies on already
  happened.
- [`tests/test_engine_source.py`](../tests/test_engine_source.py) (CF-18.02,
  [ADR 0044](adr/0044-out-of-process-engine-source-overrides.md)) —
  `test_no_generation_metadata_document_is_written` proves the `--engine-source`
  route reaches `pipeline.finalise_files` and writes no metadata document;
  `test_real_sibling_checkout_provisions_and_generates` (`@pytest.mark.e2e`)
  is the same staged/locked/finalised guarantee through a real provisioned
  engine.

When staging, finalisation, or cleanup behaviour changes, update this
contract and its executable examples in the same pull request.
