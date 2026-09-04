# 30. Validate the Data Science preview pipeline against the released engine

## Status

Accepted

## Context

[Issue #110 / CF-13.05](https://github.com/Sandsy09/create-forge/issues/110)
is the fifth and final child of
[CF-EPIC-13](https://github.com/Sandsy09/create-forge/issues/103).
CF-13.01–13.04 built the discovery-driven `--engine-preview` path: the
`forge-template>=0.4,<0.5` range ([ADR 0026](0026-adopt-the-0-4-engine-compatibility-line.md)),
the selection contract ([ADR 0027](0027-generic-component-selection-conventions.md)),
capability and platform selection ([ADR 0028](0028-discovery-driven-component-selection.md)),
and per-component options ([ADR 0029](0029-per-component-option-collection.md)).
Nothing yet *proved* that the released Data Science composition actually
traverses that path.

The coverage gap was measured, not assumed. `scientific-python` had zero
references anywhere in `tests/` — the only shipped component with none. Exactly
one fast test generated a real Data Science project, and it asserted only the
exit code. Every archetype parametrisation
(`test_pipeline.py`, `test_archetype_parity.py`, `test_e2e_engine_generation.py`)
was a hardcoded `["library", "cli"]`. No real-engine test asserted that
`spec.components.capabilities` round-trips — the one selection test that passes
capabilities stubs the engine with ids the 0.4 catalogue does not contain.

The engine model was re-checked against the installed `0.4.0`. The
`data-science` descriptor's `requires` names `jupyter>=1,<2` — the only
requirement relation in the catalogue; `scientific-python` requires nothing and
is independently optional. `plan.component_order` is composition-tier order
(`data-science`, `jupyter`, `scientific-python`); every selected component owns
at least one `PlannedFile`; `plan.files` and `rendered.files` list identical
targets in identical order. All three Data Science components declare
`options == ()`. A missing hard requirement is `invalid-component-selection`;
`library --capability jupyter` is *accepted* — Jupyter is not archetype-scoped.

One point in #110's acceptance wording needed settling against an existing
contract: #110 asks that "dry-run reports every planned target"; the canonical
[filesystem generation contract](../filesystem-generation.md) already fixes
that the engine path "lists the rendered targets and returns" writing nothing.
CF-13.05 proves that rule for the Data Science manifest rather than restating
it — the dry-run test derives its expected set from a real in-memory render of
the same selection.

## Decision

1. **Record this as its own ADR.** CF-13.01–13.04 each recorded one, and the
   two prior end-to-end-test children — CF-07.06
   ([ADR 0016](0016-end-to-end-reference-client-tests.md)) and CF-08.04
   ([ADR 0020](0020-engine-path-end-to-end-tests.md)) — did too. The
   composition under test, the auto-add boundary, the derived-assertion rule,
   and the widened guard below are decisions, not mechanical test-writing. This
   record also moves `docs/component-selection.md` and `docs/end-to-end-tests.md`
   to fully-implemented status for Stage 13.

2. **create-forge adds no component to satisfy a requirement.** When
   `data-science` is selected without `jupyter`, the request reaches the engine
   unchanged and is rejected there; `cli._missing_requirement_hint` then names
   the flag that fixes it. `create-forge` computes no requirement closure and
   never silently completes a selection — the same asymmetry ADR 0027 fixed and
   ADR 0028 implemented, now proven for the first archetype that has a hard
   requirement. The `--no-capabilities` explicit-empty form is rejected
   identically.

3. **Assertions are derived from the engine's own output, with one named
   anchor per capability.** The composition-specific tests assert
   relationships the engine reports — the `PlannedFile.owner` id set equals the
   selected ids, `plan.files` and `rendered.files` agree, the optional
   capability's contribution is exactly the symmetric difference between the
   two renders — never a copied file manifest. Two small `in`-substring anchors
   (`"notebook"` in a required-capability-owned target, `"test"` in an
   optional-capability-owned one) catch a silent "owns nothing" regression that
   the set checks alone would pass. The Data Science file manifest stays
   forge-template's to own.

4. **The e2e project carries the full composition.** `test_e2e_engine_generation.py`
   generates `data-science --capability jupyter --capability scientific-python`
   through the real console script, and runs the generated project's own
   `uv run --locked poe check` — which for Data Science includes its
   `notebook:check`, executing the starter notebook. `_ARCHETYPES` and
   `_EXTRA_ARGS` module constants replace the five hand-written
   `["library", "cli"]` parametrise lists and the session fixture's own loop,
   so a fourth archetype is a one-line change. Stage 14's entry criterion asks
   for "all three archetypes and the selected capabilities" to have executable
   evidence; a Jupyter-only render would leave `scientific-python` proven only
   in the fast suite.

5. **The three hardcoded archetype loops become discovery-driven.**
   `test_archetype_parity.py`, `test_pipeline.py`, and
   `test_component_selection.py` now parametrise over
   `Catalogue(engine.discover()).archetypes`, each with its own
   `Catalogue.required_ids(id, CAPABILITIES)` supplied — so the *same*
   parametrised parity and pipeline tests pass for three archetypes with no
   archetype-specific branch and no requirement id written down. This is itself
   the proof for #110's "no create-forge branch selects behavior by a
   hard-coded Data Science component ID".

6. **The AST guard widens from comparison operands to any string literal.**
   `test_archetype_parity.py::test_no_shipped_module_hardcodes_a_discovered_component_id`
   walked only `ast.Compare` operands (CF-08.03's original form). It now walks
   every `ast.Constant` `str` in `cli`/`prompts`/`pipeline`/`spec`/`engine.py`,
   closing the dict-key, `in {"…"}` membership, `match`/`case`, and
   `.startswith` forms an archetype-specific special case would take once `==`
   is unavailable. The five modules pass unchanged today — the widening costs
   no production change and is adopted because it makes the genericity
   guarantee real.

7. **A new canonical doc carries the acceptance evidence.**
   `docs/data-science-preview-validation.md` maps CF-EPIC-13's seven acceptance
   criteria and #110's five to the named tests proving each — the create-forge
   counterpart to forge-template's `docs/data-science-validation.md`. It is
   linked from `CLAUDE.md` and `CONTRIBUTING.md`, with a
   `…_doc_is_linked_from_canonical_entry_points` case in
   `tests/test_engine_contract.py` keeping it discoverable.

## Consequences

- No shipped module changes. `tests/test_data_science_pipeline.py` is new — the
  composition-specific proofs against the real installed engine (owner
  attribution, optional-capability differential, `spec.components` round-trip,
  staging/lock/finalisation, the five no-partial-project failure cases,
  dry-run, and interactive required-capability pre-locking).
- `tests/test_archetype_parity.py`, `tests/test_pipeline.py`, and
  `tests/test_component_selection.py` replace their `["library", "cli"]`
  parametrisations with discovery-driven ones; `test_archetype_parity.py`'s
  guard widens to every string literal.
- `tests/test_e2e_engine_generation.py` gains a `data-science` entry and the
  `_ARCHETYPES` / `_EXTRA_ARGS` constants. `.github/workflows/ci.yml`'s `e2e`
  job `timeout-minutes` rises 30 → 45 as insurance against the third full
  render plus its dependency-heavy `poe check`; no new job, and `all-green`'s
  `needs` list is unchanged.
- `docs/data-science-preview-validation.md` is new.
  `docs/end-to-end-tests.md`, `docs/component-selection.md`,
  `docs/cli-conventions.md`, `docs/component-discovery.md`,
  `docs/project-spec-construction.md`, `docs/filesystem-generation.md`,
  `docs/engine-resolution.md`, and `docs/integration-contract.md` retire their
  forward references to CF-13.05 and link this record; `CLAUDE.md`,
  `CONTRIBUTING.md`, `README.md`, and the roadmap records follow. This ADR
  closes CF-EPIC-13.
- This is **not** the CLI cutover. `--engine-preview` stays hidden and
  dev-only; the default `new` path stays direct-Copier with a bundled
  registry, and a `create-forge` install without the `engine` extra is
  untouched. Installed-console release validation and create-forge publication
  remain Stage 14 (CF-14.02, CF-14.04).
