# FT-EPIC-19 — Streamlit Architecture Contracts

## Outcome

Complete the provider-owned outcomes of streamlit architecture contracts
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

- [FT-19.01](https://github.com/Sandsy09/forge-template/issues/157)
  — Define the Streamlit project shape and ownership
- [FT-19.02](https://github.com/Sandsy09/forge-template/issues/158)
  — Define Streamlit composition, compatibility and acceptance

## Exclusions

- No work outside the assigned stage outcomes; unrelated operational issues
  and completed roadmaps remain unchanged.
- No arbitrary remote component registry or plugin execution; no new shared
  Forge runtime dependency for generated projects.
- No cloud deployment, container orchestration, authentication, database or
  FastAPI surface. No engine-default switch as part of Streamlit delivery.

## Dependencies

- Blocked by
  [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157).

Provider adoption must use a reviewed immutable release, never a moving
branch. Local candidate pairing is validation evidence, not publication.

## Parent epic

None; this is a repository-owned stage epic.

## Milestone

Streamlit Architecture Contracts — Stage 19

## Roadmap

[Stage 19](https://github.com/Sandsy09/forge-template/blob/main/docs/roadmap-v4/roadmap/19-streamlit-architecture-contracts/README.md)

## Labels

`area:template`, `area:docs`, `type:epic`, `priority:medium`, `roadmap:19`,
`cross-repo`, `status:blocked`

## Required completion evidence

- Completed native child relationships, linked acceptance evidence and
  reconciled traceability/index records.
- Immutable release receipts only where this stage owns publication;
  otherwise accepted contracts or validation receipts.
