# 25. Prompt the engine path from discovery, not the Copier registry

## Status

Accepted

## Context

[Issue #91](https://github.com/Sandsy09/create-forge/issues/91) was filed by
CF-08.03's archetype-parity review
([ADR 0019](0019-cli-archetype-parity-review.md)), which found and
deliberately declined to fix a real defect: `--engine-preview` reused
`templates.toml`'s Library-shaped registry questions for every archetype,
since the bundled registry has exactly one template. Measured against the
real installed engine:

| Registry question | Reaches ProjectSpec for `library`? | for `cli`? |
| --- | --- | --- |
| `project_name`, `project_description`, `license` | yes | yes |
| `build_backend`, `versioning` | yes, via `map_legacy_library_answers` | discarded |
| `github_org`, `type_checking`, `use_docs` | discarded | discarded |

The archetype was also selected *after* these answers were collected, so a
user building a CLI Application still answered `build_backend`/`versioning`
before they were silently dropped. Interactively, the two selections asked
"What are you building?" twice in a row — once for the Copier template
(there is only ever one, so this prompt was always vacuous), once for the
engine archetype.

ADR 0019 declined to fix this because doing so changes two things
`docs/cli-conventions.md` stated as deliberate for `--engine-preview`:
reusing the Copier path's answer collection ("no parallel prompt flow"), and
rejecting a non-empty destination before any engine call. Both are
`--engine-preview` contract changes a `size:s`, `type:decision` review is the
wrong place to make unilaterally, so #91 was filed as standalone backlog
instead of fixed in place.

`ComponentDescriptor.options` already carries everything a prompt needs —
confirmed against the installed `forge-template 0.3.1`:

```text
cli      | archetype | options: (none)
library  | archetype | packaging_mode  string  default 'uv-build-static'
                      |   choices ('uv-build-static','hatchling-static','hatchling-vcs')
                      | initial_version string  default '0.1.0'  format 'pep440'
```

## Decision

`--engine-preview` prompts from `ComponentDescriptor.options` directly and
stops reading `templates.toml` at all. Concretely:

1. **`src/create_forge/prompts.py` gains a second, independent prompt set.**
   `PROJECT_PROMPTS` asks exactly the three CLI-collected answers that reach
   `ProjectSpec.project` (`project_name`, `project_description`, `license`);
   `ask_component_options` renders a selected archetype's own declared
   `options` natively, dispatching on each option's `type`
   (`string`/`string` with `choices`/`boolean`/`integer`/`string_list`)
   rather than coercing them through the Copier-shaped `PromptSpec`, whose
   `str | bool` fields would be lossy for the other two types. An optionless
   descriptor (`cli`'s today) returns `{}` immediately, prompting for
   nothing.

2. **Archetype selection moves ahead of answer collection.** `cli.new()`
   never calls `load_registry`, `_select_template`, or `ask_all` on this
   path; `_run_engine_preview` discovers the catalogue, resolves the
   archetype (explicit `--archetype`, `--yes`-requires-one, or a single
   `choose_archetype` prompt — now the *only* "What are you building?"), and
   only then prompts for that archetype's own project and option answers.
   The destination is therefore only fully known once a project name has
   been collected.

3. **The non-empty-destination check splits into two, not one.** When
   `--path` is given explicitly, it is checked before the engine is even
   imported — preserving the common case's "before any engine call"
   guarantee exactly. The final destination (which may instead derive from
   an interactively-collected project name) is checked again immediately
   before any ProjectSpec construction, validation, or render begins — still
   before every side effect that writes anything. `discover_components()`
   itself reads the installed catalogue and writes nothing, so running it
   ahead of a destination that is not yet knowable introduces no new
   filesystem risk.

4. **ADR 0019's legacy `build_backend`/`versioning` → `packaging_mode`
   mapping survives as a `--data`-only fallback**, not a prompted path. An
   answer's preset is split by the selected descriptor's declared option
   names: a key matching one is a component-option answer; everything else
   (including `build_backend`/`versioning`, and any other Copier-registry key
   with no ProjectSpec home, such as `github_org`) lands in the project
   answers `pipeline._resolved_component_options` already inspects when the
   caller supplies no explicit `component_options`. A directly-answered
   `packaging_mode` (from a prompt or `--data`) is passed as explicit
   `component_options` and bypasses the legacy derivation entirely, matching
   how an explicit `component_options` was already documented to take
   precedence.

5. **`--template`, `--template-url`, and `--ref` are rejected outright with
   `--engine-preview`,** rather than silently ignored as before. Once the
   engine path reads no registry and clones no template, combining any of
   them with `--engine-preview` can only reflect a misunderstanding of what
   the flag does; refusing is the same call already made in reverse for
   `--archetype` without `--engine-preview`.

`--archetype`'s own resolution rules (explicit id, `--yes`-requires-one,
interactive prompt, unknown-id rejection) are unchanged — only what happens
*after* an archetype is chosen is new. Nothing added here compares against a
hardcoded component id, so ADR 0019's own AST regression guard
(`tests/test_archetype_parity.py::test_no_shipped_module_hardcodes_a_discovered_component_id`)
continues to hold without modification.

## Consequences

- `--engine-preview --archetype cli` asks no Library-specific question;
  `--archetype library` asks exactly `packaging_mode` and `initial_version`;
  the interactive flow asks "What are you building?" exactly once. All three
  are #91's acceptance criteria, made executable in
  `tests/test_cli.py`'s new engine-native-prompting block, against the real
  installed engine.
- `docs/cli-conventions.md`'s `--engine-preview` section is rewritten: the
  "reuses the same answer collection … no parallel prompt flow" and "rejects
  a non-empty destination before any engine call" claims are replaced with
  the split-check rule above, and ADR 0019's consumed/discarded prompt table
  is replaced with the new flow.
- `docs/project-spec-construction.md`'s field-mapping table and "Unmapped
  answers" section now describe directly-prompted descriptor options as the
  primary path and the legacy `build_backend`/`versioning` derivation as its
  `--data`-only fallback.
- `_select_archetype` now returns the chosen `ComponentDescriptor` itself
  (via the `ArchetypeChoice` Protocol), not just its id, so its `options` are
  available without a second discovery lookup.
- No `forge-template` change: this is create-forge-only, and the engine's
  descriptors already carried exactly the shape this needed.
