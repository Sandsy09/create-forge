# CF-EPIC-18 — Engine-Default Client Delivery and Validation

## Outcome

Complete the client-owned outcomes of engine-default client delivery and
validation through its bounded child issues.

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

- [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)
  — Adopt the released provider and implement engine-default selection
- [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159)
  — Implement secure engine-source overrides
- [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160)
  — Complete engine generation finalisation, Git and hooks
- [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)
  — Implement engine-native project updates
- [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162)
  — Preserve legacy Copier workflows and implement transition handling
- [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163)
  — Complete installed cutover regressions and migration documentation
- [CF-18.07](https://github.com/Sandsy09/create-forge/issues/164)
  — Publish and verify the engine-default client release

## Exclusions

- No work outside the assigned stage outcomes; unrelated operational issues
  and completed roadmaps remain unchanged.
- No arbitrary remote component registry or plugin execution; no new shared
  Forge runtime dependency for generated projects.

## Dependencies

- Blocked by [FT-17.06](https://github.com/Sandsy09/forge-template/issues/155).
- Blocked by [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156).

Provider adoption must use a reviewed immutable release, never a moving
branch. Local candidate pairing is validation evidence, not publication.

## Parent epic

None; this is a repository-owned stage epic.

## Milestone

Engine-Default Client Delivery and Validation — Stage 18

## Roadmap

[Stage
18](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v3/roadmap/18-engine-default-client-delivery-and-validation/README.md)

## Labels

`area:cli`, `area:docs`, `type:epic`, `priority:medium`, `roadmap:18`,
`cross-repo`, `status:blocked`

## Required completion evidence

- Completed native child relationships, linked acceptance evidence and
  reconciled traceability/index records.
- Immutable release receipts only where this stage owns publication;
  otherwise accepted contracts or validation receipts.
