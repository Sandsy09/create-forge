# 27. Select components from discovery, with owner-qualified options

## Status

Accepted

## Context

[Issue #107 / CF-13.02](https://github.com/Sandsy09/create-forge/issues/107)
is the second child of
[CF-EPIC-13](https://github.com/Sandsy09/create-forge/issues/103). It is a
contract, not an implementation: it fixes the CLI conventions for selecting
capabilities and platforms and for supplying per-component options, so that
CF-13.03 (selection), CF-13.04 (options), and CF-13.05 (pipeline proof) are
mechanical rather than design work.

[ADR 0026](0026-adopt-the-0-4-engine-compatibility-line.md) moved the
supported range to `forge-template>=0.4,<0.5`, so `engine.discover()` now
returns five descriptors. The CLI cannot yet use three of them:
`_run_engine_preview` builds `SelectionRequest.of(archetype=…)` with
`capabilities`/`platforms` left absent, and `data-science` — which hard-
requires `jupyter` — is unreachable through any invocation. [ADR
0025](0025-engine-native-prompt-flow.md) already established the shape this
extends: `--engine-preview` prompts from discovered `ComponentDescriptor`
data, reads no registry, and selects the archetype before collecting an
answer.

The engine model was checked against the installed `0.4.0` before this
decision. `ComponentDescriptor.kind` is `Literal["archetype", "capability",
"platform"]`; `ComponentSelection` carries `archetype: str`, `capabilities`,
and `platforms`; `component_options` is a top-level
`dict[kebab-id, dict[snake_name, JsonValue]]`. A `ComponentRelation` carries
only an `id`, never a kind. Component ids match
`^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$` and option names match `^[a-z][a-z0-9_]*$`,
so neither can contain `.` and an id can never contain `_`. Every model is
`strict=True`, so the engine will not coerce `"3"` to `3`. The catalogue
ships three archetypes, two capabilities, and zero platforms; `library` is
the only component with any options, and both of its options are `string`.

## Decision

1. **Publish the contract as `docs/component-selection.md`.** A new canonical
   living document, in the idiom of `docs/component-discovery.md` and
   `docs/project-spec-construction.md`. `docs/cli-conventions.md` gains a
   short pointer section, not the full contract, and remains the home of the
   exit-status table it already owns.

2. **Five hidden flags, `--engine-preview`-only.** `--capability ID`,
   `--platform ID` (both repeatable), `--no-capabilities`, `--no-platforms`,
   and `--component-option ID.OPTION=VALUE` (repeatable). Each is `hidden`,
   carries the `"Development-only: "` help prefix, and exits `1` without
   `--engine-preview` — the exact treatment `--archetype` gets. This is not
   the CLI cutover; [ADR 0026](0026-adopt-the-0-4-engine-compatibility-line.md)
   did not perform it and neither does this.

3. **Preserve absent versus explicitly empty.** A `--no-capabilities` flag,
   or an interactive prompt confirmed with nothing ticked, records an
   explicit empty selection in `spec.SelectionRequest.explicit`; omitting the
   flags under `--yes`, or a kind with zero discovered descriptors, records
   absence. The wire payload is identical either way today — `create-forge`
   resolves no policy — but the seam ADR 0022 built exists precisely so a
   policy-aware caller of `pipeline.build_generation_request` sees the
   difference.

4. **Handle a required component asymmetrically.** Interactively it is
   pre-checked and locked in its kind's multi-select: display the user
   confirms, not a mutation. Under `--yes` nothing is added — the engine's
   own `requires selected component(s)` error is translated with a flag hint.
   `--yes` has no display, so auto-adding there would be exactly the silent
   selection mutation `docs/component-discovery.md` and forge-template's
   manifest contract forbid. `create-forge` computes no requirement closure
   and branches on no component id to decide any of this.

5. **Owner-qualified options only.** `--component-option ID.OPTION=VALUE`,
   split on the first `.` then the first `=`. The two identifier alphabets
   make this unambiguous *by construction*, and CF-13.04 must prove colliding
   option names across components stay distinguishable — an unqualified
   shorthand would reintroduce the ambiguity that proof exists to rule out.
   An unqualified `OPTION=VALUE` is a `typer.BadParameter` usage error
   (exit `2`), as malformed `--data` already is. The ADR 0019 / ADR 0025
   legacy `build_backend`/`versioning` → `packaging_mode` derivation survives
   as a lower-precedence `--data`-only fallback, still archetype-only, still
   gated by the selected descriptor's declared option names.

6. **The client owns option-value typing; the engine owns the verdict.** A
   CLI string is converted to the declared `ComponentOption.type` before
   serialisation (`boolean` by `--data`'s `true`/`false` rule, `integer` by
   `int()`, `string_list` by comma-split, `string` verbatim) because
   `strict=True` means the engine will not. A value that will not convert is
   passed through unchanged, so the engine emits the authoritative
   `does not match its declared type` message rather than `create-forge`
   inventing a parallel one.

7. **Pre-engine checks are shape-only, against discovery.** `create-forge`
   rejects, before any engine call: a flag id absent from the discovered
   catalogue (listing the valid ids, as `--archetype` does), an id of the
   wrong kind for its flag, and a `--component-option` owner not in the
   resolved selection. Each is answerable from the descriptor list the CLI
   already holds. Requirement closure, conflicts, option domains, `choices`,
   `required`, and compatibility stay entirely engine-owned — reproducing
   them would put a second copy of the catalogue's semantics in this
   repository, and a client-side archetype/capability allowlist is
   explicitly forbidden by the
   [Data Science capability contract](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-capabilities.md).

8. **De-duplicate; deterministic order.** A repeated `--capability` value is
   de-duplicated first-seen; a repeated `--component-option` key is last-wins,
   as a repeated `--data` key already is. Options are prompted and serialised
   in the engine's own `COMPOSITION_TIER_ORDER` (`archetype`, `capability`,
   `platform`), lexical by id within a tier.

## Consequences

- `docs/component-selection.md` is added and linked from `CLAUDE.md`,
  `CONTRIBUTING.md`, and `docs/cli-conventions.md`;
  `tests/test_engine_contract.py` gains
  `test_component_selection_doc_is_linked_from_canonical_entry_points`,
  copying the existing link-audit guards.
- `tests/test_engine_cross_repository.py` gains
  `test_selection_model_matches_the_documented_contract`, pinning the three
  descriptor kinds, the `ComponentSelection` field set, the four
  `ComponentOption.type` values, the two-level `component_options` mapping,
  and the two distinct identifier alphabets — asserted from the models via
  `typing.get_args` and the `StringConstraints` metadata, never by naming a
  component. A future engine change that invalidates the contract fails here
  rather than silently.
- `docs/cli-conventions.md` gains a `## Component selection` pointer section,
  two entries in `## When prompts are skipped`, and extended examples in the
  exit-`1` and exit-`2` rows. The `` `3` `` row is untouched —
  `test_reserved_compatibility_exit_status_is_documented_once` pins it.
- Two now-false claims are corrected in the same change:
  `docs/project-spec-construction.md`'s "no discovered descriptor of either
  kind exists yet" and `docs/organisation-policy-consumption.md`'s "(which
  ships only `library` and `cli`)". The `CF-13.02–13.04` forward references
  in `docs/component-discovery.md`, `docs/integration-contract.md`,
  `docs/engine-resolution.md`, and `docs/project-spec-construction.md` narrow
  to `CF-13.03–13.04`.
- `tests/test_archetype_parity.py::test_no_shipped_module_hardcodes_a_discovered_component_id`
  already walks every scanned module's string comparisons against the live
  discovered id set, which is now all five ids. CF-13.03 and CF-13.04
  inherit that regression guard with no new machinery — a selection branch
  that compares against `"jupyter"` or `"data-science"` fails it.
- No CLI code changes here. No Typer option, `prompts` function,
  `SelectionRequest` construction, or `pipeline` change — CF-13.03 and
  CF-13.04 own every line of that. No new option-schema vocabulary, no
  `create-forge`-owned semantic predicate, no policy resolver or `--policy`
  flag, no default-path cutover, no `pyproject.toml` version bump, and no
  `forge-template` change. The only place a production component id appears
  in this repository is the contract document's worked examples, which
  [#107](https://github.com/Sandsy09/create-forge/issues/107) permits.
