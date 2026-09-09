# GitHub filing record and reconciliation procedure

## Filing status

The issues, labels, milestones and native relationships were filed and verified
on 2026-09-09. The manifest and issue indexes record their durable URLs and
numbers. The temporary resumable receipt remains outside repository history.

The shared label source is `.github/labels.toml`, byte-identical in both
repositories. New stage labels are `roadmap:15` through `roadmap:21`.
Every issue's complete label set, owner, title, body path, milestone, parent
and direct blockers appear in [the manifest](filing-manifest.json).

## Classification and relationships

- Epics use `type:epic`, `priority:medium`, one stage and `cross-repo`.
- Children have exactly one type, size, priority and stage, with relevant areas.
- `cross-repo` marks boundary contracts, release hand-offs, adoption and direct
  cross-repository validation, not every provider content change.
- Decision children carry `status:needs-decision`; blocked entries carry
  `status:blocked` until their open direct predecessors are resolved.
- `breaking-change` marks CF-18.01's default switch. Classify additional
  breaking work only after the contract's compatibility review.
- Do not assign people, due dates or GitHub Projects without a separate choice.
- Milestones exist only in repositories owning an epic for that stage.
- Children attach to their repository-local epic through native sub-issues.
  Blocked-by edges remain native issue dependencies, including cross-repo
  edges. Do not replace child-level gates with whole-epic dependencies.

## Verified filing procedure

1. Run the checker from the repository root against both roadmap checkouts.
   Validate **both** manifests together, even when filing only one roadmap.
   Read the current GitHub API documentation at filing time before selecting
   native sub-issue/dependency endpoints; this document does not freeze an API.
2. Inspect all historical issues in both repositories, not only open issues.
   Immediately before **each** creation, search by exact stable identifier and
   compare the exact full title. A token search alone is not proof of identity.
   Reuse an exact matching issue only after verifying its body/owner. Stop on
   collisions, multiple matches or a closed issue with conflicting scope;
   never silently create a second issue or reopen an old one.
3. Create/reuse only required labels and exact-title milestones. Use the shared
   manifest; do not prune unrelated labels or replace unrelated metadata.
   Preserve existing milestone dates and assignments unless approved.
4. Create/reuse the eight epics first. Then create/reuse children in a
   topological order of `blocked_by` across both packs. The first child is
   FT-15.01. Each body path is relative to its roadmap root, **not** to the
   manifest's directory. Read the complete UTF-8 file for the body; never use
   an empty body or a title/labels-only placeholder.
5. Keep a local resumable receipt outside commits. For every entry record
   stable identifier, repository, numeric issue number, API node ID, URL,
   submitted body hash and completion state for creation, body-link resolution,
   parent attachment, dependency attachment and verification. Persist each
   successful operation before continuing.
6. When both endpoint IDs exist, replace draft links to issue IDs with actual
   repository-qualified issue links throughout bodies. Resolve remaining
   relative documentation links to the owning repository's merged `main`
   paths. Keep the original bodies available for review; do not submit raw
   relative draft links as if GitHub issue rendering could resolve them.
7. Attach each child to its native parent and add every direct blocked-by edge,
   including epic gates on boundary children. Read existing relationships
   first and add only missing ones. Existing unrelated edges require review,
   not deletion. Relationship failure is a partial failure, not permission to
   fall back to body-only dependency claims.
8. Re-read every issue and compare repository, exact title, complete resolved
   body, labels, open state, milestone, parent and native direct blockers.
   Verify the full graph remains acyclic and all child membership is present.
   Update `status:blocked` from actual open blockers; do not copy stale status
   labels from completed historical roadmap issues.
9. Return all resulting URLs and any partial failure. On retry, repeat the
   exact-title/identifier checks even when a receipt exists. If an issue was
   created but its response was lost, recover it by exact match rather than
   creating another.
10. Update both roadmap indexes and dependency mirrors through documentation
    PRs with verified GitHub links. GitHub bodies and native relationships are
    authoritative; reviewed contract changes must reconcile both mirrors before
    dependent implementation begins.

## Release and contract safeguards

Accepting FT-15.04 unblocks client contract design; FT-17.06's immutable
provider publication unblocks client adoption. Do not make CF-16.01 wait for
that release. The final client cutover publication requires FT-18.01 and
CF-18.06, including engine-native and legacy updates.

FT-19.01 begins after CF-16.03. FT-19.02 chooses the actual Streamlit target
provider line and adds only necessary implementation prerequisites before
FT-20.01 starts. Do not add CF-18.07 as an automatic blocker. If cutover has
not shipped, CF-21.01 must retain engine-preview and plain-install optionality.
