# 45. Run the engine `new` Git/hook lifecycle in a new module, and refuse the
    excluded targets it makes load-bearing

## Status

Accepted

## Context

ADR 0041 (CF-16.02) decided the engine `new` finalisation lifecycle -- `git
init`, one initial commit, conditional `pre-commit install --install-hooks`,
and the committed `.forge/generation.json` metadata document -- as the engine
analogue of `forge-template`'s `copier.yml` `_tasks`
(`docs/engine-project-lifecycle.md`). CF-18.03 (#160) is that implementation,
and inherits two questions ADR 0041 explicitly left open:

- **Where does the lifecycle live?** `pipeline.py` depends on `engine.py`
  transitively and is therefore not itself required to stay engine-free, but
  `staging.py` is engine-free by construction
  ([ADR 0015](0015-staged-filesystem-generation.md)) so it ships in the wheel
  and runs in the fast suite with no `engine` extra installed. The lifecycle
  needs neither property of the engine -- it only spawns `git`/`uv` and reads
  one rendered filename -- so it should not be forced into either existing
  module for convenience.
- **The `_exclude` parity row.** `forge-template`'s `copier.yml` declares
  `_exclude: [copier.yml, "~*", "*.py[co]", __pycache__, .git, .DS_Store]` --
  paths Copier never writes into a generated project.
  `forge-template`'s own `docs/engine-default-parity.md` assigns this row to
  `create-forge` as "client staging filter; the engine renders only declared
  component content," with **no filed issue other than CF-18.03**. The engine
  never emits any of these targets today, but nothing in `engine.py`,
  `pipeline.py`, or `forge_template`'s own contract stops a future component
  from emitting one, and CF-18.03 changes the stakes: this issue makes the
  engine `new` path run `git init` at the final destination *after* the
  rename, which means a rendered `.git/hooks/pre-commit` would no longer be
  inert clutter -- `git init` does not clobber an existing `.git/hooks/`
  directory, so that file would survive re-initialisation and later execute
  as a real Git hook.

## Decision

1. **A new engine-free module, `create_forge.lifecycle`.** One function,
   `finalise_project(dst: Path) -> tuple[str, ...]`, run by
   `pipeline.finalise_files` only after the atomic rename succeeds -- the
   same absolute-path reason `docs/filesystem-generation.md` already gives
   for why the direct-Copier `_tasks` cannot be staged. It imports nothing
   from `forge_template`, not even under `TYPE_CHECKING`, and is added to
   `tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard alongside
   `staging.py`/`sources.py`/`compat.py`/`engine_source.py`.

2. **`finalise_project` never raises.** `git init` failure skips every later
   step (nothing else can succeed without a repository); a failed `git add`
   skips only the commit (hook installation needs `.git/` but not a commit);
   every other failure is independent. Each failure becomes one warning
   naming the exact manual command that finishes the step, collected and
   returned in order. `pipeline.finalise_files`/`finalise_generation_request`
   both grow a `tuple[str, ...]` return value carrying these warnings;
   `cli.py` prints each and `new` still exits `0` (ADR 0041 rule 4 -- a sound
   render is not worth discarding for a convenience step). No warning ever
   includes raw subprocess stdout or stderr, mirroring
   `staging.create_uv_lock`'s and `engine_source.py`'s existing rule, since a
   `uv run` failure can carry package-index credentials.

3. **Hooks install via `uv run --directory <dst> pre-commit install
   --install-hooks`, gated on the rendered file, not a component id.** `uv
   run --directory` implicitly creates/syncs `.venv` from the staging-created
   `uv.lock` before invoking `pre-commit` -- one command standing in for the
   direct-Copier `_tasks`' separate `uv sync --all-groups` + `uv run
   pre-commit install`. The client checks `(dst /
   ".pre-commit-config.yaml").exists()` -- the rendered file it already
   holds -- never a component id, per
   [`docs/component-selection.md`](component-selection.md)'s no-allowlist
   rule.

4. **The generation-metadata document is written into the staging tree,
   before the rename, not appended after it.** `pipeline.finalise_files`
   gains a `metadata_json: str | None` keyword; when given, it is written at
   `engine.generation_metadata_target()` (re-exported from
   `forge_template.DEFAULT_GENERATION_METADATA_TARGET` rather than duplicated
   as a second `.forge/generation.json` literal) through the same
   `staging.write_files` target-safety pass every rendered file gets. The
   re-export is a lazily-imported function, not a module-scope name: an
   installed engine outside `compat.SUPPORTED_ENGINE_RANGE` may predate this
   constant entirely (published only at the `0.5.0` cutover, FT-17.01), and a
   module-level `from forge_template import DEFAULT_GENERATION_METADATA_TARGET`
   in `engine.py` would turn that mismatch into a misleading "engine not
   installed" `ImportError` raised the moment `engine.py` is imported --
   before `negotiate_protocol`'s own compatibility check ever gets to run and
   raise the intended `EngineCompatibilityError`. This was caught by
   `tests/test_e2e_engine_generation.py::test_an_out_of_range_engine_is_rejected_before_any_write`
   against a real, genuinely out-of-range installed engine, not a
   monkeypatched one. Writing the metadata document keeps the atomic-rename
   guarantee whole: there is no window where `dst` exists without its own
   provenance document, and a metadata-write failure is an ordinary staging
   failure (cleans up, exits `1`), not a special case.
   `finalise_generation_request` fails closed with a `StagingError` *before
   any write* if `RenderedProject.metadata` is `None` -- the installed
   0.5-line engine always returns one, so a `None` here is a provider-
   contract violation, and a silently un-updatable project is worse than an
   explicit exit `1`. `--engine-source` (ADR 0044 rule 29) calls
   `finalise_files` with no `metadata_json`, unchanged: it still writes no
   metadata document, but now gets the same Git/hook lifecycle as the
   default route, since `git init` is unrelated to update-eligibility and
   the success panel already says the project is not updatable.

5. **`staging.write_files` refuses the `_exclude` denylist, not just Copier's
   `copier.yml` entry.** Extending the existing target-safety pass
   (`_safe_relative_path`) that already refuses an absolute, drive-qualified,
   or `..`-containing target: a `.git` path segment anywhere, `*.py[co]`,
   `__pycache__`, a `~`-prefixed name, or `.DS_Store` now abort the whole
   `write_files` call with nothing written, the same posture as an escape
   attempt. Refused, not silently skipped -- a silently dropped engine
   target is exactly the class of quiet wrong-scaffold invariant 1 already
   warns about for registry prompt keys. `copier.yml` itself is recorded as
   **not applicable, not refused**: it is a template-source file Copier had
   to avoid copying into its own output, and the engine has no equivalent
   input to accidentally re-emit -- it renders only declared component
   content, so there is nothing at that path to refuse.

## Consequences

- `create_forge.lifecycle` ships as a new module, engine-free by
  construction, in `_SHIPPED_MODULES`.
- `pipeline.finalise_files`/`finalise_generation_request` change signature:
  both now return `tuple[str, ...]` instead of `None`, and
  `finalise_generation_request` can raise `StagingError` for a `None`
  metadata document before any write. Every existing caller and test that
  constructs a `RenderedProject` for `finalise_generation_request` must
  supply a real `metadata`; `--engine-source`'s route is unaffected since it
  already calls `finalise_files` directly.
- `create_forge.engine` gains one new function, `generation_metadata_target()`,
  which imports `forge_template.DEFAULT_GENERATION_METADATA_TARGET` lazily
  inside its own body rather than at module scope, for the compatibility
  reason above.
- `docs/filesystem-generation.md`'s "still contains no `.git`, `.venv`,
  hooks, or pre-commit installation" sentence is now false for the default
  and `--engine-source` routes; it moves to describe the post-rename
  lifecycle in force. `docs/engine-project-lifecycle.md` moves ADR 0041
  rules 1-5 out of its "decided" voice; rules 6-23 (engine-native update)
  stay decided, CF-18.04's.
- An engine-generated project with the `pre-commit` capability selected now
  ends generation with a populated `.venv` (created by `uv run
  --install-hooks`); one without the capability does not. Documented in
  `docs/filesystem-generation.md` rather than left as a surprise.
- No `forge-template` change (CF-ROADMAP-01-EX-01): the metadata document's
  shape, `DEFAULT_GENERATION_METADATA_TARGET`, and `RenderedProject.metadata`
  are all already shipped in the installed `forge-template 0.5.0`.
