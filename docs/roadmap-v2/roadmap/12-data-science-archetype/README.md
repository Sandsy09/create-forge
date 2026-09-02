# Stage 12 — Data Science Archetype

## Epic

[FT-EPIC-12 / forge-template#98](https://github.com/Sandsy09/forge-template/issues/98)
adds the third production archetype and publishes a consumable engine release.

## Dependencies

FT-EPIC-12 is natively blocked by FT-EPIC-11.

## Child sequence

1. [FT-12.01 / #109](https://github.com/Sandsy09/forge-template/issues/109)
   implements the independent `data-science` archetype with its hard Jupyter
   requirement.
2. [FT-12.02 / #110](https://github.com/Sandsy09/forge-template/issues/110)
   adds its clean starter notebook and documented data/model/artefact layout.
3. [FT-12.03 / #111](https://github.com/Sandsy09/forge-template/issues/111)
   validates supported compositions and all three archetype regressions.
4. [FT-12.04 / #112](https://github.com/Sandsy09/forge-template/issues/112)
   publishes and verifies the `forge-template` 0.4.0 compatibility line.

The four children form a strict sequence beginning after FT-11.04.

## Entry criteria

- Stage 11 capabilities are production-ready.
- The Stage 10 contract supplies complete generated-project acceptance rules.

## Outcomes

- Add an independent Data Science manifest and owned content tree.
- Implement the package-plus-notebooks shape through reviewed extensions.
- Compose supported capability combinations without implicit mutation.
- Validate restoration, locking, packaging, imports, notebooks, and tests.
- Prove Library and CLI Application behavior remains unchanged.
- Publish the compatible engine line required by create-forge Stage 13.

## Exit criteria

The installed engine catalogue discovers and renders Data Science from a
released, verified package, with no cross-archetype resource access and no
Forge dependency in generated projects.

## Non-goals

The direct-Copier tree, stored answers, and create-forge UX do not change here.
