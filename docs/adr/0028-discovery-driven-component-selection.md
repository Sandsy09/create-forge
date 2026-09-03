# 28. Select capabilities and platforms from one discovered catalogue

## Status

Accepted

## Context

[Issue #108 / CF-13.03](https://github.com/Sandsy09/create-forge/issues/108)
is the third child of
[CF-EPIC-13](https://github.com/Sandsy09/create-forge/issues/103) and the
first to write selection code. [ADR 0027](0027-generic-component-selection-conventions.md)
fixed the CLI conventions in the canonical
[component selection contract](../component-selection.md); this record
implements the capability and platform half of it and settles the questions
that contract deferred to implementation.

Before ADR 0027, `_run_engine_preview` built
`SelectionRequest.of(archetype=…)` with `capabilities` and `platforms` left
absent. The `>=0.4,<0.5` line ([ADR 0026](0026-adopt-the-0-4-engine-compatibility-line.md))
discovers five descriptors — three archetypes, two capabilities, zero
platforms — and one archetype hard-requires a capability, so it could not be
generated through any invocation.

The engine model was re-checked against the installed `0.4.0`.
`discover_components()` returns descriptors already sorted by id. A
`ComponentRelation` carries only `id` and `version`, never a kind, so a
requirement's kind is only knowable by resolving that id back through the
catalogue. Every `forge_template` model is `strict=True` and
`extra="forbid"`. `forge_template.composition.COMPOSITION_TIER_ORDER` is
`("archetype", "capability", "platform")` but is not part of the public
facade. `questionary` 2.1.1's `checkbox` has two relevant behaviours: its
select-all key resets `selected_options` to `[]` wholesale — clearing
`disabled` entries too — and its arrow-key handler loops
`while not is_selection_valid()`, which never terminates if every entry is
disabled.

## Decision

1. **Publish nothing new; implement the accepted contract.** ADR 0027 and
   `docs/component-selection.md` already define the flag surface, precedence,
   diagnostics, and validation ownership. This record only fixes the internal
   shape and the questionary-specific handling that contract left open, and
   moves `docs/component-selection.md`'s `## Status` to "implemented for the
   two selectable kinds".

2. **One discovered `Catalogue`, threaded through the pipeline.**
   `pipeline.discover_catalogue()` wraps a single `engine.discover()` in a
   frozen `Catalogue` with kind-grouped access (`archetypes`, `of_kind`,
   `get`, `kind_of`, `required_ids`). `cli.py` discovers it once for
   archetype *and* capability/platform selection and passes it to
   `build_generation_request(…, catalogue=…)`, so `engine.discover()` runs
   exactly once per `--engine-preview` invocation (#108's "discover once").
   `discover_archetypes()` stays as the archetype-only view — ADR 0017 and
   ADR 0019 name it and those records are immutable — but `cli.py` no longer
   calls it, so the two never run back to back. `Catalogue` is the single
   place descriptor `kind` and `requires` are read; `cli.py` never inspects
   either.

3. **`Catalogue.required_ids` is direct-only.** It resolves a descriptor's
   own `requires` tuple, filtered to one kind, and computes no transitive
   closure. `create-forge` surfaces exactly what discovery reports and adds
   nothing — the engine rejects a missing hard dependency rather than a
   client silently satisfying it
   ([component manifests](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)).

4. **A kind with nothing selectable is not prompted, and not explicit.**
   When every discovered descriptor of a kind is required by the chosen
   archetype, `create-forge` selects those ids without offering a choice and
   records the kind as *not* explicit in `SelectionRequest` — the same
   reasoning as `_select_archetype`'s skip-when-only-one case, one tier down:
   no alternative was offered, so a policy default could still legitimately
   have applied. `SelectionRequest.of` gains
   `capabilities_explicit`/`platforms_explicit` overrides for exactly this
   case, symmetric with the existing `archetype_explicit`. This case is
   unreachable in `0.4.0`; it is defined so a future archetype cannot produce
   undefined behaviour, and it also sidesteps questionary's all-disabled
   arrow-key loop.

5. **Required entries are locked in the multi-select, then reinstated.** A
   required id renders `checked=True`, `disabled="required by <archetype-id>"`
   — visible and annotated — and `choose_components` unions the required ids
   back into its result after the prompt returns. The reinstatement is
   load-bearing: questionary's select-all key clears disabled entries, so
   `disabled=` is presentation only. Only ids shown as locked are reinstated,
   so this stays "the user saw and confirmed it", never a computed closure.

6. **Deterministic prompt order.** Archetype, then capabilities, then
   platforms — `forge_template.composition.COMPOSITION_TIER_ORDER`, mirrored
   as `spec.DESCRIPTOR_KIND`'s declaration order rather than imported, since
   that submodule is not public. All component selection precedes all project
   answers, so the destination-deriving project name stays last (ADR 0025's
   ordering). Within a multi-select, entries keep discovery order — the
   engine owns presentation.

7. **Client-side checks are shape-only.** `_validate_flag_ids` rejects, before
   any engine call, an id absent from the catalogue (listing the valid ids,
   as `--archetype` does) and an id whose discovered kind is wrong for its
   flag; both exit `1`. It de-duplicates repeated flag values first-seen. The
   `--yes` missing-requirement hint (`Add --capability <id>.`) is appended to
   the engine's own translated error, computed from `Catalogue.required_ids`
   — `create-forge` still adds nothing to the request. No client-side
   archetype or capability allowlist exists.

## Consequences

- `pipeline.py` gains `Catalogue`, `discover_catalogue()`, `DESCRIPTOR_KIND`
  handling, and a `catalogue=` keyword on `build_generation_request`;
  `discover_archetypes()` becomes a one-line view. `spec.py` gains
  `DESCRIPTOR_KIND`, `SELECTABLE_KINDS`, and the two `*_explicit` overrides on
  `SelectionRequest.of`. `prompts.py` gains `COMPONENT_PROMPTS` and
  `choose_components`. `cli.py` gains four hidden `--engine-preview`-only
  options (`--capability`, `--no-capabilities`, `--platform`,
  `--no-platforms`), a `ComponentFlags` value object, and the
  `_resolve_selection` / `_resolve_kind` / `_validate_flag_ids` /
  `_missing_requirement_hint` helpers.
- `tests/test_component_selection.py` is new: the flag surface, the
  absent-versus-explicit table, required pre-locking and the toggle-all
  reinstatement, prompt order, the zero-descriptor and all-required kinds,
  the `--yes` hint, and single-discovery. `tests/test_pipeline.py` gains the
  `catalogue=` reuse case; three interactive `tests/test_cli.py`
  `--engine-preview` cases now fake `questionary.checkbox`.
- `docs/component-selection.md`, `docs/cli-conventions.md`,
  `docs/component-discovery.md`, and `docs/project-spec-construction.md` move
  to the present tense for the two selectable kinds and link this record;
  `CLAUDE.md`, `CONTRIBUTING.md`, and `README.md` follow.
- `tests/test_archetype_parity.py::test_no_shipped_module_hardcodes_a_discovered_component_id`
  already walks `cli`/`prompts`/`pipeline` string comparisons against all
  five live ids, so a selection branch that compares against `"jupyter"` or
  `"data-science"` fails it with no new machinery.
- This is **not** the CLI cutover. Every flag stays hidden and
  `--engine-preview`-only; per-component option collection
  (`--component-option`, type coercion) is CF-13.04, and the
  end-to-end preview-pipeline proof is CF-13.05. The default `new` path stays
  direct-Copier, and a `create-forge` install without the `engine` extra is
  untouched.
