# CF-EPIC-16 — Engine-Default Client Contracts

## Outcome

Complete the client-owned outcomes of engine-default client contracts through
its bounded child issues.

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

- [CF-16.01](https://github.com/Sandsy09/create-forge/issues/155)
  — Define engine-default selection and source-resolution UX
- [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156)
  — Define update dispatch, migration and filesystem lifecycle
- [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157)
  — Approve coordinated cutover acceptance and support policy

## Exclusions

- No work outside the assigned stage outcomes; unrelated operational issues
  and completed roadmaps remain unchanged.
- No arbitrary remote component registry or plugin execution; no new shared
  Forge runtime dependency for generated projects.

## Dependencies

- Blocked by [FT-15.04](https://github.com/Sandsy09/forge-template/issues/149).

Provider adoption must use a reviewed immutable release, never a moving
branch. Local candidate pairing is validation evidence, not publication.

## Parent epic

None; this is a repository-owned stage epic.

## Milestone

Engine-Default Client Contracts — Stage 16

## Roadmap

[Stage 16](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v3/roadmap/16-engine-default-client-contracts/README.md)

## Labels

`area:cli`, `area:docs`, `type:epic`, `priority:medium`, `roadmap:16`,
`cross-repo`, `status:blocked`

## Required completion evidence

- Completed native child relationships, linked acceptance evidence and
  reconciled traceability/index records.
- Immutable release receipts only where this stage owns publication;
  otherwise accepted contracts or validation receipts.
