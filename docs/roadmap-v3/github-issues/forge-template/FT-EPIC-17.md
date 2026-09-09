# FT-EPIC-17 — Engine-Default Provider Implementation and Release

## Outcome

Complete the provider-owned outcomes of engine-default provider implementation
and release through its bounded child issues.

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

- [FT-17.01](https://github.com/Sandsy09/forge-template/issues/150)
  — Implement provider provenance and public metadata contracts
- [FT-17.02](https://github.com/Sandsy09/forge-template/issues/151)
  — Implement approved platform compositions
- [FT-17.03](https://github.com/Sandsy09/forge-template/issues/152)
  — Complete approved generated-content parity
- [FT-17.04](https://github.com/Sandsy09/forge-template/issues/153)
  — Implement reproducible rendering for engine updates
- [FT-17.05](https://github.com/Sandsy09/forge-template/issues/154)
  — Validate provider parity, reproducibility and distributions
- [FT-17.06](https://github.com/Sandsy09/forge-template/issues/155)
  — Publish and verify the reviewed cutover provider release

## Exclusions

- No work outside the assigned stage outcomes; unrelated operational issues
  and completed roadmaps remain unchanged.
- No arbitrary remote component registry or plugin execution; no new shared
  Forge runtime dependency for generated projects.

## Dependencies

- Blocked by [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157).

Provider adoption must use a reviewed immutable release, never a moving
branch. Local candidate pairing is validation evidence, not publication.

## Parent epic

None; this is a repository-owned stage epic.

## Milestone

Engine-Default Provider Implementation and Release — Stage 17

## Roadmap

[Stage
17](https://github.com/Sandsy09/forge-template/blob/main/docs/roadmap-v3/roadmap/17-engine-default-provider-implementation-and-release/README.md)

## Labels

`area:template`, `area:docs`, `type:epic`, `priority:medium`, `roadmap:17`,
`cross-repo`, `status:blocked`

## Required completion evidence

- Completed native child relationships, linked acceptance evidence and
  reconciled traceability/index records.
- Immutable release receipts only where this stage owns publication;
  otherwise accepted contracts or validation receipts.
