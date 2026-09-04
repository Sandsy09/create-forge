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

## Engine lock finalisation

`staging.create_uv_lock` executes the fixed command directly, without a shell,
after all reviewed files are present and before the staging context renames the
tree. `create-forge[engine]` includes `uv>=0.12,<0.13`; the default Copier path
does not gain another uv dependency or task.

A missing executable, process-launch error, or non-zero resolver status becomes
an actionable `StagingError`. Raw subprocess output is not exposed because
resolver diagnostics and package-index URLs can contain credentials. The
staging context removes the incomplete tree and leaves the destination
untouched. Successful engine output contains `uv.lock`, but still contains no
`.git`, `.venv`, hooks, or pre-commit installation.

## Target safety

`staging.write_files` resolves every `(target, content)` pair the engine
hands back before writing anything. A target is rejected — and nothing from
that call is written — if it is absolute, drive-qualified, or contains a
`..` segment anywhere, or if its resolved path would land outside the
staging root. `RenderedFile.target` is documented as project-relative, but
this is not assumed without checking: the safety boundary belongs to
`create-forge`, the same way destination-conflict and path-traversal checks
always have.

## Finalisation and cleanup

| Path | On success | On failure |
| --- | --- | --- |
| Copier (`runner.scaffold`) | `dst` contains the completed project, written directly by Copier. | `dst` is removed if this call created it; left untouched if it pre-existed. |
| Engine (`pipeline.finalise_generation_request`) | Rendered files and `uv.lock` are complete before the staging directory is renamed to `dst`; no intermediate state is ever visible there. | Write, lock, or rename failure removes the staging directory; `dst` is left exactly as it was found — created or not. |

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
  detection; target-safety refusals (absolute, drive-qualified, `..`
  targets); staging directory placement (adjacent to `dst`, not the system
  temp directory); uv command/error translation; atomic finalisation;
  staging-tree cleanup on failure,
  including read-only files; `discard_on_failure` removing only a
  destination it created.
- [`tests/test_pipeline.py`](../tests/test_pipeline.py) —
  `finalise_generation_request` against a real `RenderedProject`, command
  ordering before rename, and write/lock failures leaving nothing behind.
- [`tests/test_cli.py`](../tests/test_cli.py) — `--engine-preview` against a
  non-empty destination exits before the engine is touched;
  `--engine-preview --dry-run` neither writes nor resolves; a lock failure
  exits `1` and writes nothing; the existing
  `test_new_engine_preview_*` characterized-failure cases assert no
  destination and no leftover staging directory.
- [`tests/test_data_science_pipeline.py`](../tests/test_data_science_pipeline.py)
  (CF-13.05) — the same guarantees for the multi-component Data Science
  composition: a full staged/locked/finalised project on disk, dry-run
  listing exactly the engine's own planned targets and writing nothing, and
  five failure modes (missing requirement, invalid option, incompatible
  engine, destination conflict, lock failure) each leaving no partial
  project and no staging sibling.
- [`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py)
  — the adopted `validate_rendered_project` contract against the real pinned
  engine, proving what `finalise_generation_request` relies on already
  happened.

When staging, finalisation, or cleanup behaviour changes, update this
contract and its executable examples in the same pull request.
