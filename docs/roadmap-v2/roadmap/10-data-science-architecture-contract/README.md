# Stage 10 — Data Science Architecture Contract

## Epic

[FT-EPIC-10 / forge-template#96](https://github.com/Sandsy09/forge-template/issues/96)
defines the contract before any component is implemented.

## Dependencies

This epic has no open native blocker. The roadmap begins only after completed
`create-forge#91` and the completed Foundation roadmap provide its accepted
engine and client baseline.

## Child sequence

1. [FT-10.01 / #101](https://github.com/Sandsy09/forge-template/issues/101)
   defines the fixed package-plus-notebooks shape and ownership.
2. [FT-10.02 / #102](https://github.com/Sandsy09/forge-template/issues/102)
   defines the optionless `jupyter` and `scientific-python` capability
   contracts and bounded dependency lines.
3. [FT-10.03 / #103](https://github.com/Sandsy09/forge-template/issues/103)
   defines notebook, data, model, secret, and generated-artefact safeguards.
4. [FT-10.04 / #104](https://github.com/Sandsy09/forge-template/issues/104)
   fixes compatibility, acceptance, and `forge-template` 0.4.0 release
   requirements.

Each child is blocked by the preceding item. FT-10.01 is the roadmap's only
initially actionable child.

## Entry criteria

- Forge Foundation Stages 00–09 are complete.
- Library and CLI Application prove independent production archetypes.
- create-forge #91 has completed engine-native option prompting.

## Outcomes

- Define the minimal package-plus-notebooks project shape.
- Assign every concern to Foundation, archetype, capability, platform,
  profile, organisation policy, or client orchestration.
- Define dependency-selection criteria rather than selecting tools by trend.
- Define data, model, secret, path, environment, and generated-artifact
  safeguards.
- Define Python, lock, packaging, notebook-validation, and maintenance
  expectations.
- Classify all protocol, public API, component, engine, and client
  compatibility impacts.

## Exit criteria

The four accepted decisions make the shape, capability boundaries,
safeguards, compatibility impact, and acceptance strategy implementation-ready.

## Non-goals

No production component, dependency, generated output, CLI behavior, tag, or
release is introduced in this stage.
