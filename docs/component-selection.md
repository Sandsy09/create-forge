# Component Selection

This is the living contributor contract for how `create-forge` turns user
input — flags and prompts — into the `components` and `component_options`
sections of a [ProjectSpec](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md).
It covers only the client's selection surface: syntax, precedence, the
absent-versus-empty distinction, deterministic prompt order, and which
failures `create-forge` reports itself versus which it forwards from the
engine. The canonical
[component manifest](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md),
[Data Science capability](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-capabilities.md),
and [extension-point](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md)
contracts remain owned by `forge-template`; every semantic rule below stays
there.

It is a sibling of the [component discovery contract](component-discovery.md)
(how the descriptors this document selects from are obtained) and the
[ProjectSpec construction contract](project-spec-construction.md) (how the
resulting selection is mapped onto the wire payload), and it extends
[`docs/cli-conventions.md`](cli-conventions.md)'s `--engine-preview` section.

## Status

Accepted as a contract under [ADR 0027](adr/0027-generic-component-selection-conventions.md).
This document is the design; the code that satisfies it is filed separately.
CF-13.03 ([#108](https://github.com/Sandsy09/create-forge/issues/108))
implements capability and platform selection, CF-13.04
([#109](https://github.com/Sandsy09/create-forge/issues/109)) implements
per-component option collection, and CF-13.05
([#110](https://github.com/Sandsy09/create-forge/issues/110)) proves the whole
path against the released engine. Until those land, `--engine-preview` selects
an archetype and nothing else — the rules here describe the target the three
issues build toward, not current behaviour.

This is **not** the CLI cutover. Every flag below is hidden and reachable only
via `new --engine-preview`; the default `new` path stays direct-Copier with a
bundled registry, exactly as [ADR 0026](adr/0026-adopt-the-0-4-engine-compatibility-line.md)
left it.

## The selection surface

`new` gains five hidden options, each carrying the `"Development-only: "` help
prefix that `--archetype` already uses and each rejected with exit `1` when
supplied without `--engine-preview` — byte-for-byte the treatment
`--archetype` gets today:

| Flag | Repeatable | Effect |
| --- | --- | --- |
| `--capability ID` | yes | Adds `ID` to `SelectionRequest.capabilities` → `components.capabilities`. |
| `--no-capabilities` | no | Records an explicit *empty* capability selection. |
| `--platform ID` | yes | Adds `ID` to `SelectionRequest.platforms` → `components.platforms`. |
| `--no-platforms` | no | Records an explicit *empty* platform selection. |
| `--component-option ID.OPTION=VALUE` | yes | Sets `component_options[ID][OPTION]`. |

`--archetype` is unchanged: still hidden, still resolved against
`pipeline.discover_archetypes()`, still the single "What are you building?"
prompt when omitted interactively.

`--capability` / `--no-capabilities` (and the platform pair) are mutually
exclusive; supplying both is a contradiction and exits `1`.

## Absent versus explicitly empty

Protocol v1 distinguishes "no explicit choice for this kind — a policy default
may still apply" from "an explicit choice of none". `create-forge` collects no
organisation policy, so the two currently produce the same wire payload, but
the distinction is preserved through `spec.SelectionRequest.explicit` for a
policy-aware caller of `pipeline.build_generation_request` — see the
[downstream policy-consumption contract](organisation-policy-consumption.md).
CF-13.03 must encode it exactly:

| Input | `capabilities` | Recorded in `explicit`? |
| --- | --- | --- |
| neither flag; `--yes` | `()` | no — absent |
| neither flag; interactive prompt shown, nothing ticked | `()` | yes — explicit "none" |
| `--no-capabilities` | `()` | yes — explicit "none" |
| `--capability x` (with or without `--yes`) | `("x",)` | yes |
| kind has zero discovered descriptors | `()` | no — never prompted |
| `--capability x` **and** `--no-capabilities` | — | rejected, exit `1` |

`explicit` is consumption-side bookkeeping only; it never becomes a field of
the ProjectSpec wire payload, which always emits both `capabilities` and
`platforms` as arrays (empty when unselected). Platforms follow the identical
table.

## Required components

An archetype may declare a hard requirement — the descriptor exposes it as a
`ComponentRelation` carrying only an `id`, so its kind is resolved by looking
that `id` up in the discovered catalogue. `create-forge` surfaces the
requirement; it never satisfies it silently:

- **Interactively**, a required component appears in its kind's multi-select
  pre-checked, annotated `(required by <archetype-id>)`, and cannot be
  unticked. It is part of the submitted selection because the user saw and
  confirmed it.
- **Under `--yes`**, nothing is added. A missing requirement reaches the
  engine, which rejects it with
  `component '<archetype>' requires selected component(s): <id>`;
  `create-forge` translates that through `engine.explain` and appends the flag
  that supplies it (`Add --capability <id>.`).

`create-forge` must not compute a requirement closure, inject a missing
component into `SelectionRequest`, or branch on a component id to do either.
This mirrors `forge-template`'s own rule that "the engine rejects a missing
hard dependency rather than silently modifying ProjectSpec; clients may guide
users or profiles may supply defaults, but the final request remains
observable and complete"
([component manifests](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)).

## Prompt flow and order

Deterministic, and a superset of [ADR 0025](adr/0025-engine-native-prompt-flow.md)'s
engine-native flow. All component selection precedes all answer collection, so
the destination-deriving project name is still collected last:

```
1. archetype        prompts.choose_archetype             unchanged; skipped when exactly one
2. capabilities     multi-select, required pre-locked     skipped if --capability/--no-capabilities given,
                                                            or zero capability descriptors discovered
3. platforms        multi-select, required pre-locked     skipped if --platform/--no-platforms given,
                                                            or zero platform descriptors discovered
4. project answers  prompts.ask_project_answers           unchanged: project_name, project_description, license
5. component options  prompts.ask_component_options       per selected component, in the order below
```

Component options are prompted, and serialised into `component_options`, in
the engine's own composition-tier order — `archetype`, then `capability`, then
`platform` (`forge_template.composition.COMPOSITION_TIER_ORDER`) — and
lexically by component id within a tier. A selected component that declares no
options produces no prompt and no `component_options` key.

Cancelling any prompt (Ctrl-C / Ctrl-D) exits `130` with nothing written, as
`cli-conventions.md`'s cancellation rule already requires.

## `--component-option` syntax

`ID.OPTION=VALUE`. Parse by splitting on the **first `.`** for the owner id,
then the **first `=`** in the remainder for the option name; the value keeps
any further `.` or `=`. The two identifier alphabets make this unambiguous by
construction — a component id matches `^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$` (never
a `.` or `_`) and an option name matches `^[a-z][a-z0-9_]*$` (never a `.` or
`-`).

Only the owner-qualified form is accepted. An unqualified `OPTION=VALUE` is a
usage error (exit `2`), reported with the owning component it needs:
`--component-option needs an owning component id, e.g. library.OPTION=VALUE`.

### Precedence for a component option's value

Highest wins:

1. `--component-option ID.OPTION=VALUE` — owner-qualified, explicit.
2. `--data OPTION=VALUE` where `OPTION` is a name the **selected archetype's**
   own descriptor declares — the unqualified archetype-inferred preset split
   ADR 0025 already performs. Never applies to a capability or platform
   option.
3. The legacy `--data build_backend` / `--data versioning` →
   `packaging_mode` derivation via `engine.map_legacy_library_options`, gated
   by the selected archetype descriptor declaring `packaging_mode`
   (ADR 0019, ADR 0025). Archetype-only, and only when 1 and 2 supplied
   nothing for that name.
4. The descriptor's own declared default.

An interactive prompt for an option occupies the same slot as rule 1 — a
prompted value and a `--component-option` value never both apply, because a
`--component-option` preset suppresses that option's prompt exactly as a
`--data` preset suppresses a registry question.

### Option value typing

Every `forge-template` model is `strict=True`, so it will not coerce `"3"` to
`3` or `"true"` to `True`. A value collected as a CLI string must be converted
to the declaring `ComponentOption.type` before it is serialised:

| Declared type | Conversion |
| --- | --- |
| `string` | verbatim |
| `boolean` | case-insensitive `true` / `false`, as `--data` already parses |
| `integer` | `int(value)` |
| `string_list` | comma-split, each item trimmed, empties dropped — the same rule `ask_component_options`'s own `string_list` prompt uses |

A value that will not convert is **passed through unchanged**, so the engine
produces the authoritative
`option '<name>' value '<v>' does not match its declared type` message rather
than `create-forge` inventing a parallel one.

## Validation ownership

| `create-forge` rejects, before any engine call | `forge-template` rejects, translated via `engine.explain` |
| --- | --- |
| any of the five flags without `--engine-preview` — exit `1` | a missing hard `requires` |
| `--capability` with `--no-capabilities` (or the platform pair) — exit `1` | a `conflicts` violation |
| `--component-option` with no `.` or no `=` — exit `2`, `typer.BadParameter`, as malformed `--data` | an option name no `options_schema` declares |
| `--capability` / `--platform` / `--component-option` naming an id absent from the discovered catalogue — exit `1`, listing the valid ids as `--archetype` already does | an option value outside `choices`, of the wrong type, or a missing `required` one |
| an id selected under the wrong kind for its flag (`--capability` naming an archetype) — exit `1` | ProjectSpec protocol or Python-range incompatibility — exit `3` |
| `--component-option` whose owner id is valid but not in the resolved selection — exit `1` | the generated project failing its own validation |

Every left-column check is answerable from the descriptor list alone — an
id's existence, its `kind`, and whether it is in the current selection set.
None reproduces a semantic predicate. In particular `create-forge` ships **no
archetype/capability allowlist**: a future compatibility restriction "must use
the existing component relationship and version contracts rather than a
client-side allowlist"
([Data Science capabilities](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-capabilities.md)).

## Duplicates and repetition

`--capability x --capability x` de-duplicates, preserving first-seen order
(the engine sorts `capabilities` lexically regardless). A repeated
`--component-option` for the same `ID.OPTION` takes the last value, exactly as
a repeated `--data` key does. Neither is an error — a repeated flag is a
scripting artefact, not a semantic statement.

## Kinds with no discovered descriptors

A kind for which discovery returns nothing is never prompted, and
`--capability` / `--platform` naming an id of that kind produces the
unknown-id rejection. `--no-capabilities` / `--no-platforms` stay legal and
record an explicit empty selection. This is the real state of `platform` in
`forge-template 0.4.0` — the kind, the `components.platforms` array, and the
composition tier all exist, but the catalogue ships zero platform components —
and the contract treats it as the ordinary zero case, not a special one.

## Compatibility with the shipped archetypes

`--engine-preview --archetype library` and `--archetype cli` must behave
identically before and after CF-13.03 / CF-13.04: no new required flag, and no
new prompt for `cli` (which declares no options) or beyond `packaging_mode` /
`initial_version` for `library`. The Copier default `new` path and a
`create-forge` install without the `engine` extra are untouched.

## Worked examples

These use production component ids purely to illustrate flag syntax — the one
place [#107](https://github.com/Sandsy09/create-forge/issues/107) permits
them; no shipped module or test may name one.

```bash
# archetype with its one required capability, non-interactive
create-forge new "Risk Models" --engine-preview \
    --archetype data-science --capability jupyter --yes

# add an independently optional capability
create-forge new "Risk Models" --engine-preview --archetype data-science \
    --capability jupyter --capability scientific-python --yes

# explicit "no capabilities", plus an owner-qualified archetype option
create-forge new "Credit Risk Utils" --engine-preview --archetype library \
    --no-capabilities \
    --component-option library.packaging_mode=hatchling-vcs --yes
```

## Executable examples

The contract will be characterised by:

- [`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py)
  — `test_selection_model_matches_the_documented_contract` pins the engine
  facts this document is built on (the three descriptor kinds, the
  `ComponentSelection` fields, the four option types, the two-level
  `component_options` mapping, and the two distinct identifier alphabets), so
  a future engine change that invalidates the contract fails here.
- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py) —
  `test_component_selection_doc_is_linked_from_canonical_entry_points` keeps
  this document discoverable.
- **CF-13.03** adds `tests/test_cli.py` / `tests/test_prompts.py` cases for
  the flag surface, the absent-versus-empty table, required pre-locking, and
  the deterministic prompt order.
- **CF-13.04** adds the owner-qualified parsing, per-type coercion, and
  colliding-option-name fixture cases.
- **CF-13.05** adds the end-to-end preview-pipeline proof against the released
  engine.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
