# 46. Apply the engine-native update client-side with `git merge-file`, and
    reproduce the old render with a version-match short-circuit

## Status

Accepted

## Context

ADR 0041 (CF-16.02) decided the engine-native `update` rules -- file-based
routing, a Git-backed three-way merge from a clean working tree, a genuine
per-target `--dry-run`, printed-not-run rollback, and an opt-in degraded
two-way fallback -- as `docs/engine-project-lifecycle.md` rules 6-23.
CF-18.04 (#161) is that implementation, and resolves what ADR 0041 left to
it: the merge mechanism, how the *old* render is reproduced, and the shape of
the degraded algorithm the provider explicitly declines to compute.

The installed `forge-template 0.5.0` ships more of this than ADR 0041
assumed when it was written. `forge_template.plan_update(recorded, *, old,
new) -> UpdatePlan` already performs the reproducible-render classification:
target-by-target `unchanged`/`added`/`removed`/`changed`/`renamed`,
owner-declared rename-window resolution (`recorded < since <= installed`),
and digest verification of the supplied `old` against the recorded
document's `output` entries -- failing closed as `invalid-generation-metadata`
if `old` does not match, and as `unsupported-generation-metadata` /
`provider` if `old` is empty against a non-empty recorded `output`. So
`create-forge` must not re-implement any classification, digest check, or
rename-window logic (CF-ROADMAP-01-EX-01, and this issue's own Exclusions);
it owns exactly: routing, the Git working tree, reproducing *old*, the
per-target merge, and presentation.

Three findings shape the design below:

- `plan_update`'s digest check makes a wrong `old` render impossible to apply
  silently -- so a cheap reproduction strategy that is sometimes wrong is
  still safe, as long as it fails rather than lies.
- `parse_generation_metadata` (the *reproduce* entry point) requires each
  recorded component version to equal the installed one -- it is **not** an
  update pre-check. Only `plan_update`, which reads leniently
  (`require_version_match=False`), is used here.
- `reproduction` on `GenerationMetadata` is written by the *client*, never
  the engine: `plan_update` always returns `reproduction=ReproductionRecord(mode="exact")`,
  and `GenerationMetadata` is frozen, so recording `"degraded"` is a
  `model_copy(update={...})` the client performs itself.

## Decision

1. **A new engine-free module, `create_forge.update`.** Routing
   (`route_for`), lenient structural parsing of the recorded document
   (`read_recorded`), the clean-tree precondition (`require_clean_tree`),
   rename application (`apply_renames`), the merge (`merge_target`),
   per-target application of a classified plan (`apply_plan`), the degraded
   algorithm (`degraded_plan`), staging (`stage_result`), and the `uv.lock`
   refresh (`relock`). Added to `tests/test_engine_contract.py`'s
   `_SHIPPED_MODULES` guard. It consumes the engine's `UpdateTarget`/
   `AppliedRename` **structurally**, through `UpdateTargetView`/
   `AppliedRenameView` -- `Protocol`s mirroring `descriptors.py`'s
   `DescriptorView` pattern -- rather than importing either type.
   `pipeline.py` (already permitted `forge_template` types under
   `TYPE_CHECKING`, per ADR 0013) is the one module that calls both
   `engine.plan_update` and `create_forge.update`, handing the real engine
   objects to the structural module across that seam.

2. **`engine.py` imports `GenerationMetadata`/`UpdatePlan`/`plan_update`
   lazily, not at module scope.** All three are `0.5.0`-only additions
   (FT-17.01/FT-17.04), exactly like `DEFAULT_GENERATION_METADATA_TARGET`
   before it (ADR 0045). A first pass put them in `engine.py`'s ordinary
   top-level `forge_template` import block; a real (not mocked) e2e run
   against a genuinely out-of-range installed engine
   (`tests/test_e2e_engine_generation.py::test_an_out_of_range_engine_is_rejected_before_any_write`)
   caught the identical bug ADR 0045 already fixed once: the module-scope
   import raised `ImportError` before `negotiate_protocol`'s own
   compatibility check ever ran, turning the intended
   `EngineCompatibilityError` into a misleading "engine not installed"
   message. Fixed the same way: `GenerationMetadata`/`UpdatePlan` are
   type-checking-only imports (used solely in annotations, postponed by
   `from __future__ import annotations`), and `plan_update`/
   `ReproductionRecord` are imported inside `engine.plan_update`'s and
   `engine.metadata_json`'s own function bodies, reached only after the
   compatibility checks each function already runs. `ReproductionRecord` is
   the runtime-constructed name; `UpdatePlan`/`GenerationMetadata` never
   need a real import at all, since a type annotation under postponed
   evaluation is never evaluated. This ADR records the pattern explicitly so
   a third instance of the same class of bug does not need a third real e2e
   failure to catch it: **any name a supported engine has that an
   out-of-range one might not must be imported lazily, after a compatibility
   check, never at `engine.py` module scope.**

3. **The old render: short-circuit on a version match, else provision
   out-of-process.** `pipeline._reproduce_old` compares the recorded
   `provider.version` against `engine.get_info().package_version`. Equal --
   the common case, and every no-op or repeated update -- reuses the
   already-computed `new` render's own bytes with no second render and no
   provisioning at all, correct because decision 7 below fixes the
   *effective* spec to the recorded spec verbatim: identical spec plus
   identical engine version is definitionally the same render. Different,
   the recorded release is provisioned through the existing `--engine-source`
   machinery (ADR 0044) via a new `engine_source.released_requirement(version)`
   (`forge-template==<version>`, a third source kind alongside
   `build_requirement`'s path/VCS/scp forms) and rendered there.
   `EngineSourceError`/`EngineCompatibilityError` from that path becomes
   `pipeline.UnavailableRecordedReleaseError` -- ADR 0041 rules 21-22's
   "unavailable recorded release" signal, carrying the recorded version so
   the caller can name it in the required axis/detected-value/action report.
   No forge-template release before `0.5.0` ever writes generation metadata,
   so no real project can record an *older* release today; the provisioning
   branch is proven by fast fakes plus one `@pytest.mark.e2e` run against the
   `../forge-template` sibling checkout as a stand-in recorded release (the
   same pattern CF-18.02 used, which caught a real `NameError` the mocked
   tests missed) -- not against a genuine older release, because none exists.

4. **The merge is `git merge-file -p`, not a bespoke algorithm.** `git` is
   already a hard runtime dependency since CF-18.03; reusing it for the merge
   means create-forge never re-implements what Git already does correctly and
   every user of `update` already knows the markers for. `merge_target`
   writes `base`/`ours`/`theirs` to scratch files, reads merged bytes from
   `-p`'s stdout, and treats a negative or >127 exit status (`git
   merge-file`'s own documented "negative on error, count of conflicts
   otherwise, truncated to 127" contract) as a genuine failure rather than a
   conflict count. A target whose working-tree bytes still match the
   reproduced `old` bytes is written outright with no merge at all -- both a
   fast path and the only path that keeps binary content free of spliced
   markers.

5. **A binary or otherwise non-mergeable `changed` target is decided by
   pristine-ness alone.** `_looks_like_text` is a NUL-byte sniff. Pristine
   (matches the recorded/reproduced old bytes) is always replaced outright,
   text or not. Locally modified and not text is left completely untouched
   and reported `conflict` for manual reconciliation -- `git merge-file`
   would otherwise splice text conflict markers into arbitrary binary
   content, corrupting it.

6. **A target the user deleted locally is left deleted.** A `changed`/
   `unchanged` classification whose working-tree path no longer exists is
   reported `skipped`/left absent, never resurrected from the new render --
   symmetric with ADR 0041 rule 13's already-decided "a locally-modified
   `removed` target is left in place, the user decides" posture, applied to
   the mirror case rule 13 did not name.

7. **The effective spec for an update is always the recorded spec verbatim.**
   `update` gains no selection flags; re-selecting components on update is
   regeneration, not this issue's scope, and ADR 0041 named no such flag.
   `--ref` (the Copier route's target-version flag) is therefore rejected
   outright on the engine route, exit `1`, naming `--legacy` as where it
   applies -- the engine route's "target" is always the installed
   `forge-template` release, moved only by upgrading `create-forge` itself.

8. **`--degraded` is pristine-only replace, decided from recorded digests, not
   a reproduced render.** `forge_template.plan_update` explicitly states the
   degraded comparison is "the client's to make; this engine never performs
   that comparison" -- so `update.degraded_plan` is entirely create-forge's
   own code, and deliberately the most conservative algorithm available: a
   working-tree target whose bytes still hash to its recorded `output` digest
   (from `.forge/generation.json`, not a reproduced old render, since none
   exists on this path) is replaced with the new render; anything else --
   including every genuinely locally-modified file -- is left completely
   alone and reported for manual review. No merge base is ever invented.
   Taking this path, whether by `--degraded` or by declining
   `_confirm_degraded`'s prompt after an `UnavailableRecordedReleaseError`,
   records `reproduction.mode = "degraded"` with a reason on the persisted
   document (rule 22), via a new `engine.metadata_json(metadata, *,
   degraded_reason=None)` that performs the `model_copy` `GenerationMetadata`
   being frozen requires.

9. **`uv.lock` is re-locked after a successful merge; a failure warns.**
   `uv.lock` is client-owned (ADR 0021) and never one of the engine's
   classified targets, so a dependency-affecting merge needs its own refresh
   step. `update.relock` calls `staging.create_uv_lock` and converts a
   `StagingError` into a warning rather than failing the whole update --
   the same warn-and-continue posture `lifecycle.py`'s own convenience steps
   already use (ADR 0045), applied here to the update path's equivalent.

10. **Write order: merge, then `uv.lock`, then `.forge/generation.json` last,
   then one `git add -A`.** Rule 19's "written last" is about the *last
   write*, not a separate staging call after every step -- one `git add -A`
   at the very end covers the merged targets, the relocked lock, and the
   refreshed metadata together, which is simpler than staging after each
   write and still satisfies "the recorded spec still describes the last
   good state" until every write has actually succeeded.

## Consequences

- `create_forge.update` ships as a new module, engine-free by construction,
  in `_SHIPPED_MODULES`.
- `create_forge.engine` gains `plan_update` (the compatibility-checked
  wrapper, mirroring `render()`/`validate()`'s shape) and `metadata_json`
  (the `to_json()`/`model_copy` wrapper for both the exact and degraded
  cases).
- `create_forge.engine_source` gains `released_requirement(version)`, a third
  source kind alongside `build_requirement`'s path/VCS/scp forms.
- `create_forge.pipeline` gains `UnavailableRecordedReleaseError`,
  `UpdatePreparation`, `prepare_update`, and `prepare_degraded_update` -- the
  one place old/new reproduction and classification are orchestrated,
  consistent with `pipeline.py` already being the seam allowed
  `forge_template` types under `TYPE_CHECKING`.
- `cli.py`'s `update` command gains `--legacy` and `--degraded`; `--ref` is
  now rejected outright on the engine route. The `_ensure_legacy_available`/
  `runner` import moves behind the Copier-routed branch, since an
  engine-native update must not require the optional `legacy` extra --
  fixing a latent bug where it ran unconditionally before routing.
- The success panel's "Not yet update-eligible" line is now
  "Pull later changes with: `create-forge update`" for the default engine
  `new` path -- `--engine-source` keeps its own distinct not-eligible wording
  (ADR 0044 rule 29 is unaffected: that route still writes no metadata
  document at all).
- `docs/engine-project-lifecycle.md` moves ADR 0041 rules 6-23 out of its
  "decided" voice; every rule the contract named is now shipped.
  `docs/cli-conventions.md` gains the `update` route table, the two new
  flags, and the genuine per-target dry-run list in place of the "will gain"
  paragraph.
- The `e2e-windows` job CF-18.03 added now also runs
  `tests/test_update_engine.py`, satisfying the acceptance matrix's
  Windows engine-native-update row.
- No `forge-template` change (CF-ROADMAP-01-EX-01): `plan_update`,
  `UpdatePlan`, `UpdateTarget`, `AppliedRename`, and the recorded-digest
  fields the degraded path reads are all already shipped in the installed
  `forge-template 0.5.0`.
