# 29. Collect and serialise options for every selected component

## Status

Accepted

## Context

[Issue #109 / CF-13.04](https://github.com/Sandsy09/create-forge/issues/109)
is the fourth child of
[CF-EPIC-13](https://github.com/Sandsy09/create-forge/issues/103).
[ADR 0027](0027-generic-component-selection-conventions.md) fixed the whole
component-selection contract in the canonical
[component selection contract](../component-selection.md); CF-13.03
([ADR 0028](0028-discovery-driven-component-selection.md)) implemented four of
its five flags. The fifth — `--component-option ID.OPTION=VALUE` — and
per-component option collection were still a documented target.

Option collection was archetype-only: `cli._collect_engine_answers` called
`prompts.ask_component_options` for the selected archetype alone and
`_run_engine_preview` serialised the result as `{archetype_id: answers}`. A
selected capability or platform that declared options had no way to receive a
value, and there was no owner-qualified flag. Against `forge-template 0.4.0`
this is latent — only `library` declares options — which is why closing it
generically now, before a component that needs it ships, matters.

The engine model was re-checked against the installed `0.4.0`. Every
`forge_template` model is `strict=True`, so a CLI string is not coerced to
`int`/`bool`. `ComponentOption.type` is one of `string`, `integer`,
`boolean`, `string_list`. A `component_options` namespace that ends up empty
(`{"library": {}}`) is *accepted*, so a client that wants "no key" must drop
it rather than rely on rejection. An undeclared option name, a value outside
`choices`, a wrong type, and options for an unselected component are all
engine verdicts, each with a stable `ForgeEngineError`.

Two points in the accepted contract needed settling against #109's own words:

- #109 lists "duplicate values … fail before destination effects"; ADR 0027's
  "Duplicates and repetition" says a repeated `--component-option ID.OPTION`
  takes the last value and is explicitly not an error.
- `docs/component-selection.md`'s malformed-syntax message named a production
  component id (`library`), which no shipped module may contain.

## Decision

1. **Record this as its own ADR.** CF-13.01–13.03 each recorded one; the
   legacy-fallback change and the CLI-string coercion boundary below are
   decisions, not mechanical implementation of ADR 0027. This record also
   moves `docs/component-selection.md`'s `## Status` to fully implemented.

2. **Collect options for every selected component, in one deterministic
   order.** `Catalogue.selected(selection)` returns the selected descriptors
   in composition-tier order (`archetype`, then `capability`, then `platform`
   — `DESCRIPTOR_KIND`'s declaration order, still mirrored not imported), then
   lexically by id within a tier. `prompts.resolve_component_options` walks
   that sequence, and `ask_component_options` becomes its one-descriptor
   wrapper. A component whose namespace ends up empty is omitted from the
   result entirely, so a selected optionless component produces no
   `component_options` key.

3. **A repeated `ID.OPTION` takes the last value.** Exactly as a repeated
   `--data` key does, per ADR 0027. #109's "duplicate values … fail" is read
   as "resolved deterministically before any destination effect", not
   "rejected" — `_parse_component_options` collapses repeats as it parses.

4. **The legacy Library fallback becomes a per option-name merge.** Before
   CF-13.04, `pipeline._resolved_component_options` skipped the whole legacy
   `build_backend`/`versioning` → `packaging_mode` derivation the moment
   `component_options` was non-`None` — which a selected capability's own
   namespace alone would trigger, silently defeating the archetype's
   `--data build_backend=…` fallback. It now fills only a *declared archetype
   option the caller left unset*, and merges beneath what the caller supplied
   — matching the contract's own per-name precedence
   (`--component-option` > `--data` > legacy > default). The gate is unchanged:
   the mapping applies only when the selected archetype's own discovered
   descriptor declares every name it produces (ADR 0019); no archetype id
   appears in the function.

5. **One CLI-string coercer, applied to both preset sources.**
   `prompts.coerce_option_value` sits beside `_ask_component_option`, which
   already performs the identical per-type parsing for prompted input:
   `boolean` → case-insensitive `true`/`false`, `integer` → `int(value)`,
   `string_list` → comma-split/trim/drop-empties, `string` verbatim. It is
   applied to every preset value whose option the descriptor *declares*,
   whether it came from `--component-option` (rule 1) or an archetype-name
   `--data` (rule 2). A non-`str` value (a `--data` bool) passes straight
   through; a string that will not convert also passes through, so the strict
   engine emits the authoritative `does not match its declared type` message
   rather than create-forge inventing a parallel one.

6. **The malformed-syntax message carries no production id.** It reads
   `--component-option expects ID.OPTION=VALUE, got '<value>'` (exit `2`,
   `typer.BadParameter`, like malformed `--data`). `docs/component-selection.md`'s
   one line specifying the old wording is amended to match. Production ids
   stay confined to that document's `## Worked examples` section.

7. **Client-side option checks stay shape-only.** `_validate_component_option_owners`
   rejects, before any prompt or write and exiting `1`, an owner id absent
   from the discovered catalogue (any kind may own options) and an owner id
   valid but not in the resolved selection. An option *name* the owner does
   not declare, a value outside `choices`, a wrong type, a missing `required`
   one — all remain engine verdicts, translated through `engine.explain`. No
   client-side allowlist exists.

## Consequences

- `spec.py` gains `SelectionRequest.ids_for`. `pipeline.py` gains
  `Catalogue.selected` and splits `_resolved_component_options` into a
  per-name merge plus `_legacy_archetype_options`. `prompts.py` gains
  `coerce_option_value` and `resolve_component_options`;
  `ask_component_options` is now a thin wrapper. `cli.py` gains the
  `--component-option` option, `_parse_component_options`,
  `_validate_component_option_owners`, a `ComponentFlags.options` field, and a
  generalised `_collect_engine_answers` that collects the whole selected set.
- One deliberate behaviour change to the single-descriptor path: a preset key
  the descriptor does not declare is now kept verbatim and forwarded to the
  engine, where before it was silently dropped. This is what lets the engine
  own the unknown-option-name verdict.
- `tests/test_component_selection.py` gains a `--component-option` section,
  including colliding option names proven through the real CLI with a
  synthetic archetype/capability pair. `tests/test_prompts.py` gains
  `coerce_option_value` and `resolve_component_options` cases;
  `tests/test_pipeline.py` gains the per-name legacy-merge cases; one
  `tests/test_cli.py` test repoints its patch from the removed
  `cli.ask_component_options` to `resolve_component_options`.
- `docs/component-selection.md`, `docs/cli-conventions.md`,
  `docs/component-discovery.md`, and `docs/project-spec-construction.md` move
  to the present tense for `--component-option` and per-component option
  typing and link this record; `CLAUDE.md`, `CONTRIBUTING.md`, and `README.md`
  follow.
- This is **not** the CLI cutover. Every flag stays hidden and
  `--engine-preview`-only; validating the whole Data Science preview pipeline
  against the released engine is CF-13.05. The default `new` path stays
  direct-Copier, and a `create-forge` install without the `engine` extra is
  untouched.
