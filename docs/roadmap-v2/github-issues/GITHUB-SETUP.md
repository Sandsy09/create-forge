# GitHub Setup and Taxonomy

The shared label source of truth remains `.github/labels.toml` in both
repositories. The manifests are byte-identical and extend the existing
taxonomy with `roadmap:10` through `roadmap:14`.

## Milestones

forge-template owns milestones for Stages 10, 11, 12, and 14. create-forge
owns milestones for Stages 13 and 14. Empty milestones are not created for a
repository with no work in that stage.

## Issue rules

- `type:epic`, one `roadmap:*` label, relevant `area:*` labels, and one
  `priority:*` label classify each epic.
- `cross-repo` marks every epic participating in the coordinated roadmap.
- `status:blocked` is present only while an open predecessor prevents work.
- Native GitHub dependencies are authoritative; the matrix is a readable
  mirror.
- All 24 children are attached through native sub-issues and classified with
  their stage, type, priority, size, milestone, and relevant area labels.
- `status:blocked` is applied whenever an open direct predecessor exists;
  FT-10.01 is the only initially actionable child.
- `cross-repo` is reserved for issues that publish, consume, or directly
  validate a coordinated repository boundary.
- Exact epic and child identifiers are searched before creation so filing is
  resumable.

## IDs

- `FT-EPIC-10`, `FT-EPIC-11`, `FT-EPIC-12`, and `FT-EPIC-14` belong to
  forge-template.
- `CF-EPIC-13` and `CF-EPIC-14` belong to create-forge.
- `FT-10.*`, `FT-11.*`, `FT-12.*`, and `FT-14.*` children belong to
  forge-template.
- `CF-13.*` and `CF-14.*` children belong to create-forge.
