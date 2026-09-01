# Stage 13 — Data Science CLI Integration

## Epic

[CF-EPIC-13 / create-forge#103](https://github.com/Sandsy09/create-forge/issues/103)
exposes the released Data Science composition through `new --engine-preview`.

## Dependencies

CF-EPIC-13 is natively blocked by completed `create-forge#91` and
FT-EPIC-12. The open provider epic keeps Stage 13 blocked.

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
