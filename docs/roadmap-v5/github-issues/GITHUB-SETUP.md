# GitHub filing record and reconciliation procedure

## Filing status

The 37 issues (10 epics, 27 children) were filed before this pack existed. The
pack was imported from the filed bodies, and on 2026-09-26 the labels,
milestones and native relationships were reconciled and verified against the
manifest with `scripts/roadmap_sync.py verify`.

## Provenance of traceability

The 21 September review text that produced these issues is not stored in
either repository. Traceability is therefore **derived from the filed bodies**:
every acceptance criterion and exclusion becomes an obligation
`<ID>-AC-nn` or `<ID>-EX-nn` with its owner. The validator recomputes the
expected set from the bodies, so none can be missing or drift. It does not
claim to reproduce the original review.

## Labels

The shared source is `.github/labels.toml`, byte-identical in both
repositories. Stage labels `roadmap:22` to `roadmap:29` were added and synced
with `poe labels:sync` in both repositories, then applied to every issue in its
stage.

## Milestones

One milestone per stage in each repository that owns an epic for it, titled
`<epic title> — Stage N` (stages 24 and 25 are titled per repository). No dates
or versions are promised.

| Repository | Milestone | Number |
| --- | --- | --- |
| create-forge | Update Safety and Release Assurance — Stage 22 | [14](https://github.com/Sandsy09/create-forge/milestone/14) |
| create-forge | Windows Subprocess Reliability — Stage 23 | [13](https://github.com/Sandsy09/create-forge/milestone/13) |
| create-forge | Client CI, Dependency Auditing and Roadmap Hygiene — Stage 24 | [16](https://github.com/Sandsy09/create-forge/milestone/16) |
| create-forge | CLI Orchestration Decomposition — Stage 25 | [17](https://github.com/Sandsy09/create-forge/milestone/17) |
| create-forge | Pipeline Client Adoption and Rollout — Stage 29 | [15](https://github.com/Sandsy09/create-forge/milestone/15) |
| forge-template | Provider CI, Dependency Auditing and Roadmap Hygiene — Stage 24 | [17](https://github.com/Sandsy09/forge-template/milestone/17) |
| forge-template | Engine Internal Decomposition — Stage 25 | [20](https://github.com/Sandsy09/forge-template/milestone/20) |
| forge-template | Composition Validation Capacity — Stage 26 | [21](https://github.com/Sandsy09/forge-template/milestone/21) |
| forge-template | Pipeline and Batch Job Architecture Contracts — Stage 27 | [18](https://github.com/Sandsy09/forge-template/milestone/18) |
| forge-template | Pipeline Provider Implementation and Release — Stage 28 | [19](https://github.com/Sandsy09/forge-template/milestone/19) |

Milestones of completed stages are closed.

## Native relationships

Status: **applied and verified**. All 27 child-to-epic parents are native
sub-issues (same repository) and all 18 direct blockers, including the two
cross-repository edges (`CF-EPIC-29` and `CF-29.01` blocked by `FT-28.03`), are
native `blocked_by` dependencies. Whole-epic dependencies do not replace
child-level gates. Body-link text and native state agree; `verify` fails if
either drops an edge.

## Status labels

`status:blocked` is present exactly when an issue has an open blocker.
Stale `status:in-progress` labels were removed from the five closed issues
CF-21.02, CF-22.01, CF-22.02, CF-22.03 and CF-23.01. About eighteen older
closed issues from Stages 14–18 carry stale status labels; they are historical,
were reported, and were deliberately not changed.

## Body fidelity

Each body file is the exact text filed on GitHub: LF line endings, a final
newline, and two Markdown hard-break trailing-space lines. `body_sha256` in the
manifest pins that text. The repository therefore exempts these files from the
trailing-whitespace hook and from MD013 (`.pre-commit-config.yaml`,
`.markdownlint-cli2.jsonc`). Do not reformat them.

## Procedure

1. `uv run python scripts/roadmap_sync.py reconcile` prints the plan and
   changes nothing; read it.
2. `... reconcile --apply` performs it. It reads first, only adds
   relationships, never deletes unrelated edges, and a second run is a no-op.
   A failed native write is a partial failure, never a body-only fallback.
3. `... verify` reads GitHub back and compares it with the manifest.
4. `... export --state filed` regenerates the derived files and the dated
   snapshot; then run `scripts/check_roadmaps.py`, and `--mirror` both ways.
