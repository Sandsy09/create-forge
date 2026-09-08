# FT-EPIC-20 — Streamlit Provider Implementation and Release

## Outcome

Complete the provider-owned outcomes of streamlit provider implementation and
release through its bounded child issues.

## Issue context

The released provider catalogue contains Library, CLI Application and Data
Science plus Jupyter and Scientific Python. Streamlit is future work. Accepted
cutover contracts are its scheduling gate; the full cutover release is not.

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

- [FT-20.01](FT-20.01.md) — Implement the independent Streamlit archetype
- [FT-20.02](FT-20.02.md) — Implement Streamlit tasks, safeguards and
  capability composition
- [FT-20.03](FT-20.03.md) — Validate Streamlit generated projects and
  distributions
- [FT-20.04](FT-20.04.md) — Publish and verify the reviewed Streamlit provider
  release

## Exclusions

- No work outside the assigned stage outcomes; unrelated operational issues
  and completed roadmaps remain unchanged.
- No arbitrary remote component registry or plugin execution; no new shared
  Forge runtime dependency for generated projects.
- No cloud deployment, container orchestration, authentication, database or
  FastAPI surface. No engine-default switch as part of Streamlit delivery.

## Dependencies

- Blocked by [FT-19.02](FT-19.02.md).

Provider adoption must use a reviewed immutable release, never a moving
branch. Local candidate pairing is validation evidence, not publication.

## Parent epic

None; this is a repository-owned stage epic.

## Milestone

Streamlit Provider Implementation and Release — Stage 20

## Roadmap

[Stage
20](../../roadmap/20-streamlit-provider-implementation-and-release/README.md)

## Labels

`area:template`, `area:docs`, `type:epic`, `priority:medium`, `roadmap:20`,
`cross-repo`, `status:blocked`

## Required completion evidence

- Completed native child relationships, linked acceptance evidence and
  reconciled traceability/index records.
- Immutable release receipts only where this stage owns publication;
  otherwise accepted contracts or validation receipts.
