# 17. Expose the CLI Application archetype through discovery-driven selection

## Status

Accepted

## Context

[CF-08.02 / #10](https://github.com/Sandsy09/create-forge/issues/10) asks
create-forge to expose the engine-owned CLI Application archetype "without
duplicating its generation rules, metadata, or command semantics". It was
blocked on FT-08.04 (forge-template#4). Both that issue and
[FT-08.03 / forge-template#42](https://github.com/Sandsy09/forge-template/issues/42)
closed, and `forge-template` released `v0.3.0`, whose production catalogue
ships both `library` and `cli` as real, validated archetypes.

Adopting `v0.3.0` is materially cheaper than the empty-catalogue era this
decision leaves behind. ProjectSpec protocol is unchanged at `1`; component
manifest protocol went `1` → `(1, 2)`, which still overlaps this repository's
`(1,)`. The only thing rejecting `v0.3.0` under the prior contract is the
exact-version check
(`engine.TESTED_ENGINE_PACKAGE_VERSION`). The one breaking public-facade
change — `PlannedFile.owner_component_id` becoming a discriminated
`owner: ComponentOwner | FoundationOwner` — touches no `src/` code, since
`pipeline.finalise_generation_request` only reads `request.rendered.files`,
never a plan's ownership metadata.

Three problems surfaced in scoping, all forced into view by the catalogue no
longer being empty:

1. `ProjectSpec.python` is a required field, but `templates.toml` never
   prompts `python_min_version`/`python_version` — every existing
   `--engine-preview` test supplies them via `--data`, masking that a bare
   invocation would fail at *parse*, not at `validate()` as prior docs
   (ADR 0014, `docs/end-to-end-tests.md`) stated.
2. `library`'s v0.3.0 manifest carries a `packaging_mode` option with its own
   default (`uv-build-static`); `create-forge` sent no `component_options`,
   so a user's `build_backend`/`versioning` answers would silently stop
   reaching the render.
3. ADR 0013 chose a commit SHA over a tag specifically because `v0.2.0` had
   no tag, and cutting one would have republished every template change made
   since `v0.1.1` to existing v0.1.x users in the same act — "not a side
   effect available to this decision." `v0.3.0` is now a real, independent
   release; that constraint no longer applies to naming the development pin.

Selection also needed a home. `forge-template` v0.3.0's `copier.yml` is still
Library-only — the default Copier path cannot produce a CLI Application no
matter what `create-forge` does, so exposing `cli` is only possible behind
`--engine-preview`, which is where ADR 0014 already put every other
engine-only capability.

## Decision

**Bump the development pin to `forge-template==0.3.0` at `tag = "v0.3.0"`.**
`TESTED_ENGINE_PACKAGE_VERSION` and `SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS`
move to match (`(1, 2)` — declaring only `1` would understate what the
descriptors this release actually consumes have been validated against, even
though set-overlap means a protocol-1-only engine would still pass). The
`[tool.uv.sources]` entry moves from a commit `rev` to a `tag`, since the
reason ADR 0013 gave for avoiding one no longer holds.

**Add a hidden `--archetype` option plus a discovery-driven interactive
prompt, both live only under `--engine-preview`.** `templates.toml` is left
untouched: giving the registry a `cli` entry would let `create-forge new -t
cli` (without `--engine-preview`) silently clone the Library-only
`copier.yml` and produce a Library project. `pipeline.discover_archetypes()`
filters `engine.discover()` to `kind == "archetype"`, so `cli.py` never
branches on engine-defined `kind` values itself; `prompts.choose_archetype`
mirrors `choose_template`'s shape, including its skip-when-only-one-exists
behaviour. A bare `--yes --engine-preview` with no `--archetype` is rejected
outright — the engine declares no default archetype, and
`templates.toml`'s `default_template` is a Copier-path concept this path
does not inherit.

**Derive `ProjectSpec.python`'s defaults in `spec.py` when unanswered.**
`DEFAULT_PYTHON_MINIMUM = "3.11"` / `DEFAULT_PYTHON_DEVELOPMENT = "3.13"`
mirror `copier.yml`'s own question defaults, so `--engine-preview` works
without hand-supplied `--data` and both paths agree when neither is
answered. `spec.py` stays engine-free; these are plain constants, not a call
into `forge_template`.

**Wire the legacy Library option mapping in the same PR.** `spec.py` gains
`legacy_library_answers()`, resolving `versioning_resolved` the way
`copier.yml` itself computes it (`static` when `build_backend == "uv_build"`,
else `versioning`, defaulting to `static`) — pure, and engine-free.
`engine.py` gains a thin `map_legacy_library_options()` wrapper around the
public `map_legacy_library_answers()` facade, run through the same
compatibility checks as every other operation there. `pipeline.py` calls
both, but only as a fallback when the caller supplies no explicit
`component_options` and the archetype is `library` — the one
archetype-specific branch in this codebase, and it is keyed on the engine's
own naming (`map_legacy_library_answers`) rather than a locally maintained
archetype list, so it does not grow into a registry of per-archetype special
cases here. `cli` has no options and takes this path unchanged.

## Consequences

- `--engine-preview --archetype cli` (or an interactive selection) now
  generates a real, correct CLI Application for the first time — proven
  directly against the installed `v0.3.0` engine, not a synthetic
  descriptor.
- The three "fails closed against the empty catalogue" tests
  (`test_engine_adapter.py`, `test_engine_cross_repository.py`,
  `test_pipeline.py`) become success assertions, exactly as their own
  docstrings anticipated. `PlannedFile` construction in tests migrates to the
  discriminated `owner` field; no `src/` code changes for this.
- `docs/component-discovery.md`, `docs/project-spec-construction.md`,
  `docs/cli-conventions.md`, `docs/engine-contract-tests.md`,
  `docs/engine-resolution.md`, `docs/integration-contract.md`,
  `docs/end-to-end-tests.md`, `docs/cross-repository-workflow.md`,
  `CLAUDE.md`, and `CONTRIBUTING.md` all update their "0.2.0" / commit-SHA /
  empty-catalogue statements to match. None of them are superseded by this
  record; they are living contracts this decision keeps current, per their
  own stated maintenance rule.
- `docs/end-to-end-tests.md`'s engine-path gap narrows but does not close:
  `--engine-preview` can generate today, but CF-08.04 still needs a
  *released, range-assigned* engine, which remains [#9](https://github.com/Sandsy09/create-forge/issues/9)'s
  call, not this decision's.
- CF-08.03 / [#52](https://github.com/Sandsy09/create-forge/issues/52) (the
  archetype-parity review) is unblocked: it now has two real, generated
  archetypes and one documented, justified archetype-specific branch to
  review, rather than a hypothesis about a catalogue that did not yet exist.
