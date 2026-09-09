# FT-EPIC-15 — Engine-Default Provider Contracts

## Outcome

Complete the provider-owned outcomes of engine-default provider contracts
through its bounded child issues.

## Issue context

The released baseline is create-forge 0.3.2 with default direct-Copier
generation and an optional, hidden engine preview over forge-template
>=0.4.1,<0.5. Preview generation does not provide engine-native updates. This
draft describes future work, not a shipped interface.

Provider manifests, composition, generated content and in-memory validation
stay in forge-template. Client UX, ProjectSpec construction, staging,
filesystem application, Git/hooks and error presentation stay in create-forge.

## Problem statement

The review's broad outcome needs bounded, repository-owned work with explicit
entry and exit gates. A stage is not complete merely because its design or
package has been published.

## Proposed resolution

- Coordinate the child issues below; retain their direct blockers rather than
  substituting a blanket dependency on another complete roadmap.
- Close this epic only when every child is complete and its acceptance
  evidence is reviewed. A contract gate is not an implementation or release
  gate.

## Acceptance criteria

- [ ] Every child below is complete with reviewed completion evidence and no
  unresolved blocking decision.
- [ ] All mapped source-review acceptance criteria and exclusions are
  satisfied by their named owners; publication is not inferred from a merged
  implementation.
- [ ] Provider manifests, composition, generated content and in-memory
  validation stay in forge-template. Client UX, ProjectSpec construction,
  staging, filesystem application, Git/hooks and error presentation stay in
  create-forge.

## Child issues

- [FT-15.01](FT-15.01.md) — Inventory default-Copier parity and assign ownership
- [FT-15.02](FT-15.02.md) — Define generation provenance and
  reproducible-update inputs
- [FT-15.03](FT-15.03.md) — Define platform composition and generated-tooling
  parity
- [FT-15.04](FT-15.04.md) — Define provider compatibility, failure and release
  gates

## Exclusions

- No work outside the assigned stage outcomes; unrelated operational issues
  and completed roadmaps remain unchanged.
- No arbitrary remote component registry or plugin execution; no new shared
  Forge runtime dependency for generated projects.

## Dependencies

No open predecessor. FT-15.01 is the initially actionable child.

Provider adoption must use a reviewed immutable release, never a moving
branch. Local candidate pairing is validation evidence, not publication.

## Parent epic

None; this is a repository-owned stage epic.

## Milestone

Engine-Default Provider Contracts — Stage 15

## Roadmap

[Stage 15](../../roadmap/15-engine-default-provider-contracts/README.md)

## Labels

`area:template`, `area:docs`, `type:epic`, `priority:medium`, `roadmap:15`,
`cross-repo`

## Required completion evidence

- Completed native child relationships, linked acceptance evidence and
  reconciled traceability/index records.
- Immutable release receipts only where this stage owns publication;
  otherwise accepted contracts or validation receipts.
