# GitHub Setup Guidance

## Label source of truth

`create-forge/.github/labels.toml` defines the shared label taxonomy and is
applied with `uv run poe labels:sync`. Roadmap filing extends the existing
area/type/priority/size/status groups with:

- `type:epic` and `type:decision`;
- `roadmap:00` through `roadmap:09`;
- unprefixed `cross-repo` and `breaking-change` metadata.

Use the existing `status:blocked`; do not create a second bare `blocked` label.
Every roadmap child should have one roadmap label, one type, one primary area,
one priority and one size. Use `cross-repo` only when coordination is real, and
`status:blocked` only while a prerequisite remains unresolved.

## Milestones

The live repository has these milestones:

1. Foundation Contract — Stage 00
2. Foundation Baseline — Stages 01–03
3. Runtime & Security — Stages 04–05
4. Composition Contract — Stage 06
5. CLI Scaffolding — Stage 07
6. Reference Archetypes — Stage 08
7. Blueprint Compatibility — Stage 09

## Epic and relationship rules

- Create epics only for stages with unfinished repository-local work.
- Use GitHub sub-issues for open children; record completed pre-roadmap work as
  checked evidence in the epic body rather than backfilling closed issues.
- Use native blocked-by relationships for real, filed prerequisites.
- Do not create placeholder relationships to an `FT-*` roadmap identifier that
  has not been filed in `forge-template`.
- Keep cross-repository dependencies one-way; do not model coordination as a
  circular pair of blockers.

## ID convention

Keep `CF-xx.xx` and `CF-EPIC-xx` in live issue titles alongside GitHub's issue
numbers. The current mapping lives in `create-forge/ISSUE-INDEX.md`.
