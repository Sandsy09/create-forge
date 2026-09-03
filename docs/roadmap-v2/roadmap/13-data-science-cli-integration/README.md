# Stage 13 — Data Science CLI Integration

## Epic

[CF-EPIC-13 / create-forge#103](https://github.com/Sandsy09/create-forge/issues/103)
exposes the released Data Science composition through `new --engine-preview`.

## Dependencies

CF-EPIC-13's native predecessors `create-forge#91` and FT-EPIC-12 are both
complete. CF-13.01, CF-13.02, and CF-13.03 are complete; CF-13.04 is unblocked.

## Child sequence

1. [CF-13.01 / create-forge#106](https://github.com/Sandsy09/create-forge/issues/106)
   adopts the released `forge-template` 0.4 compatibility line.
   **Complete** under
   [ADR 0026](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0026-adopt-the-0-4-engine-compatibility-line.md):
   the supported range moved to `forge-template>=0.4,<0.5` with the lock,
   diagnostics, compatibility tables, and cross-repository contract tests
   moved with it, and no component identifier or catalogue copy added.
2. [CF-13.02 / create-forge#107](https://github.com/Sandsy09/create-forge/issues/107)
   defines generic component-selection CLI conventions.
   **Complete** under
   [ADR 0027](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0027-generic-component-selection-conventions.md):
   the canonical
   [component selection contract](https://github.com/Sandsy09/create-forge/blob/main/docs/component-selection.md)
   fixes the `--capability`/`--platform`/`--component-option` surface, the
   absent-versus-explicit-empty rule, owner-qualified option syntax and
   precedence, deterministic prompt order, and the client-versus-engine
   validation split — with no CLI code and no production component id in any
   shipped module or test.
3. [CF-13.03 / create-forge#108](https://github.com/Sandsy09/create-forge/issues/108)
   implements discovery-driven capability and platform selection.
   **Complete** under
   [ADR 0028](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0028-discovery-driven-component-selection.md):
   `pipeline.Catalogue` (one discovery, grouped by kind), the four
   `--capability`/`--no-capabilities`/`--platform`/`--no-platforms` flags,
   interactive multi-selects with required entries pre-locked and reinstated,
   the absent-versus-explicit-empty encoding through `SelectionRequest`, and
   shape-only client-side checks — no production component id in any shipped
   module or test.
4. [CF-13.04 / create-forge#109](https://github.com/Sandsy09/create-forge/issues/109)
   prompts and serialises options for every selected component.
5. [CF-13.05 / create-forge#110](https://github.com/Sandsy09/create-forge/issues/110)
   validates the Data Science preview pipeline against the released engine.

CF-13.01, CF-13.02, and CF-13.03 are done; the sequence proceeds linearly
from CF-13.04 through preview-pipeline validation.

## Entry criteria

- create-forge #91 is complete.
- forge-template Stage 12 has published a compatible engine release.

## Outcomes

- Discover archetypes and applicable capabilities through the public facade.
- Prompt for component selections and declared options without hard-coded IDs.
- Preserve explicit empty selections and namespace options by owner.
- Construct, validate, render, stage, lock, and finalise through the shared
  ProjectSpec pipeline.
- Present compatibility and selection failures before destination effects.
- Preserve Library, CLI Application, default Copier, and no-engine behavior.

## Exit criteria

Interactive and non-interactive users can request a valid Data Science
composition through the preview path, with generic tests and no copied engine
semantics.

## Non-goals

The engine path does not become the default and create-forge gains no template
or component catalogue.
