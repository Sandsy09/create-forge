# CF-EPIC-21 — Streamlit Client Adoption and Rollout

## Outcome

Complete the client-owned outcomes of streamlit client adoption and rollout
through its bounded child issues.

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

- [CF-21.01](CF-21.01.md) — Adopt the released Streamlit provider
- [CF-21.02](CF-21.02.md) — Validate installed Streamlit generation and
  document usage
- [CF-21.03](CF-21.03.md) — Publish and verify Streamlit client support

## Exclusions

- No work outside the assigned stage outcomes; unrelated operational issues
  and completed roadmaps remain unchanged.
- No arbitrary remote component registry or plugin execution; no new shared
  Forge runtime dependency for generated projects.
- No cloud deployment, container orchestration, authentication, database or
  FastAPI surface. No engine-default switch as part of Streamlit delivery.

## Dependencies

- Blocked by [FT-20.04](../forge-template/FT-20.04.md).

Provider adoption must use a reviewed immutable release, never a moving
branch. Local candidate pairing is validation evidence, not publication.

## Parent epic

None; this is a repository-owned stage epic.

## Milestone

Streamlit Client Adoption and Rollout — Stage 21

## Roadmap

[Stage 21](../../roadmap/21-streamlit-client-adoption-and-rollout/README.md)

## Labels

`area:cli`, `area:docs`, `type:epic`, `priority:medium`, `roadmap:21`,
`cross-repo`, `status:blocked`

## Required completion evidence

- Completed native child relationships, linked acceptance evidence and
  reconciled traceability/index records.
- Immutable release receipts only where this stage owns publication;
  otherwise accepted contracts or validation receipts.
