# 15. Render into an adjacent staging directory and finalise by rename

## Status

Accepted

## Context

[CF-07.04](https://github.com/Sandsy09/create-forge/issues/50) is the second
child of [CF-EPIC-07](https://github.com/Sandsy09/create-forge/issues/38),
unblocked by CF-07.01 (#49, [ADR 0014](0014-lazy-engine-reachability.md)),
which made `src/create_forge/pipeline.py`'s
`build_generation_request()` reachable from `new --engine-preview` but
returns only an in-memory `GenerationRequest` — nothing consumes it, and the
flag always prints *"Nothing was written — CF-07.04 adds real staging."* The
epic's completion criterion is broader than that one gap, though: *"Failed
generation cannot leave a final partial project."* Two distinct problems
share this issue, not one:

1. **The engine path has no filesystem half.** `engine.render()` was always
   in-memory only, by design — nothing downstream of it stages or finalises
   a `RenderedProject` to disk.
2. **The shipped Copier path can leave a partial project.** `runner.scaffold()`
   points Copier directly at the final destination. A render failure, or a
   `_tasks` failure part-way through `git init` → `uv sync --all-groups` →
   `pre-commit install --install-hooks`, leaves a half-built directory behind
   with no cleanup.

The obvious single answer — stage both paths into a temporary directory and
rename it into place on success — does not survive contact with what Copier's
`_tasks` actually do. `uv sync` writes `.venv/pyvenv.cfg` and console-script
shims with **absolute paths** baked in; `pre-commit install` writes
`.git/hooks/pre-commit` the same way. All three are written *during*
`run_copy`, at whatever path `dst_path` names. Renaming the completed
directory afterward — the whole point of staging — would silently leave a
venv pointing at a path that no longer exists and a broken pre-commit hook.
Copier's own `_tasks` mechanism has no post-move hook to re-run them at the
final path. So the two problems above cannot share one mechanism: the engine
path renders and validates entirely in memory first and can be staged safely;
the Copier path cannot be staged at all, only cleaned up after a failure at
the path it already used.

A second, independent finding narrows the engine path's implementation.
`docs/integration-contract.md` already recorded that the exact development
pin (`2158c85a`) *"predates the generated-project validator and ... Stage 07
must update and test the development pair before the CLI consumes that
API."* `forge-template`'s `main` HEAD at scoping time (`bb5f6a71`, still
version `0.2.0`, `[project.dependencies]` unchanged) adds a public
`validate_rendered_project` function and calls it as the last statement of
`render_project` — so adopting that HEAD is what makes "move/commit
generated output only after validation" an engine-owned guarantee rather
than something `create-forge` would otherwise have to approximate itself.

## Decision

**Stage the engine path; clean up the Copier path.** A new, deliberately
engine-free module, `src/create_forge/staging.py`, owns both:

- `staged(dst)` is a context manager used only by the engine path
  (`pipeline.finalise_generation_request`). It creates a staging directory
  with `tempfile.mkdtemp` **adjacent to `dst`** — inside `dst.parent`, not
  the system temp directory — which is what makes the finalising
  `Path.rename` a real atomic directory rename on both NTFS and POSIX rather
  than a copy. There is deliberately no cross-volume copy fallback: that
  would silently trade the atomicity guarantee for availability, so a
  cross-volume destination fails loudly instead. On any exception, the
  staging tree is removed and `dst` is left exactly as found.
- `discard_on_failure(dst)` is a context manager used only by the Copier path
  (`runner.scaffold`). It never stages or moves anything; it records whether
  `dst` existed on entry and removes it on failure **only if this call
  created it**, so a pre-existing directory a user pointed `--path` at is
  never touched.
- `ensure_available(dst)` and `write_files(root, files)` are shared by both:
  the same non-empty-destination conflict check `runner.scaffold` already
  had, and target-safety validation (no absolute, drive-qualified, or `..`
  target may escape the staging root) for files the engine hands back as
  plain `(target, bytes)` pairs.

`staging.py` imports nothing from `forge_template`, not even under
`TYPE_CHECKING`, and joins `tests/test_engine_contract.py`'s
`_SHIPPED_MODULES` import guard — it ships in the wheel and runs in the fast
suite with no `engine` dependency group installed, serving `runner.py`
unconditionally and `pipeline.py` only inside `--engine-preview`'s already-lazy
branch.

**The development engine pin moves from `2158c85a` to `bb5f6a71`**, adopting
`validate_rendered_project` — package version, both protocol numbers, and
`[project.dependencies]` are all unaffected; this is a pin update within the
same Stage 06 development contract, not a new compatibility line.
`create-forge` does not call `validate_rendered_project` itself:
`engine.render()` already receives an already-validated `RenderedProject`,
because `render_project` calls it internally before returning.
`pipeline.finalise_generation_request`'s docstring states this ownership
explicitly, so it is not mistaken for something `create-forge` still owes.

**`--engine-preview` now writes to a real destination.** It computes `dst`
identically to the Copier path (same `slugify`/`--path` resolution, same
`ensure_available` check, run before the engine is even imported), then
finalises through `pipeline.finalise_generation_request` on success. In
practice it still writes nothing today — the empty production catalogue
fails at `validate()` before staging is ever reached — but the code path
handling a future success is real, not stubbed. `--dry-run` lists the
planned targets and returns before staging is attempted, on both paths
alike. This corrects ADR 0014's stated consequence that the flag "never
writes a destination"; that was accurate only until this issue.

## Consequences

- `create-forge --help`, `list`, `doctor`, and `new` without
  `--engine-preview` remain provably unaffected by whether `forge-template`
  is installed, even with `staging.py` now imported unconditionally at
  `cli.py`'s module level — proven the same way as ADR 0014's equivalent
  claim: a wheel built and run in an isolated environment with the
  dependency absent.
- A Copier scaffold failure at a destination `create-forge` created no
  longer leaves a partial project behind; a failure at a destination that
  already existed before the command ran leaves it exactly as it was found.
- An `--engine-preview` failure — at protocol negotiation, validation,
  rendering, or staging itself — leaves neither a partial destination nor a
  leftover `.create-forge-*` staging directory.
- The Copier path's absolute-path `_tasks` problem is not solved, only
  routed around: `create-forge` still cannot safely move a directory Copier
  has already run `uv sync`/`pre-commit install` inside. Running Copier's
  own generation *against* a staging directory and only running `_tasks`
  after the move is future work, not part of this decision.
- The engine pin has now moved once already within the unreleased `0.2.0`
  development contract. Adopting it required updating the pin, the lockfile,
  `tests/test_engine_contract.py`'s SHA constant, and every doc that quoted
  the old one — the same mechanical cost every future development-pin move
  will carry until #9 assigns a real runtime range.
- Neither the runtime engine dependency nor `--engine-preview`'s retirement
  is decided here; both remain blocked on
  [#9](https://github.com/Sandsy09/create-forge/issues/9).
