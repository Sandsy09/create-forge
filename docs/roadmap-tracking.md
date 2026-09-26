# Roadmap tracking conventions

Living contract for how roadmap issues are recorded, labelled, grouped and
kept consistent between GitHub, the roadmap packs and both repositories
(FT-24.03, [forge-template ADR 0078](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0078-synchronise-roadmap-mirror-and-tracking.md)).
The packs are `docs/roadmap-v3`, `-v4` (frozen, as filed) and
[`docs/roadmap-v5`](roadmap-v5/README.md) for Stages 22–29. Each pack is
mirrored byte-for-byte in `create-forge`.

## Authority

GitHub issue bodies and native relationships are authoritative. A pack records
the exact filed body (LF, final newline) with its `body_sha256`, the graph, and
a dated snapshot. Completed packs are never rewritten; a later stage gets a
new pack.

Live state is deliberately **not** frozen in a manifest: open or closed and
`status:*` labels change, and only the dated snapshot in a pack's `ROADMAP.md`
mentions them. That snapshot is regenerated, never hand-edited.

## Labels

`.github/labels.toml` is the shared source, byte-identical in both repositories,
synced with `uv run poe labels:sync`. Every stage has a `roadmap:N` label
(`roadmap:22` to `roadmap:29` for pack v5) that is applied to every issue of
that stage. The body's Labels section must equal the manifest's `labels`;
`roadmap:N` is added on top and recorded as `added_labels`.

## Milestones

One milestone per stage in each repository that owns an epic for it, titled
`<that repository's epic title> — Stage N` (the two repositories may title a
stage differently). No dates or versions are promised. A milestone is closed
when every issue of that stage in that repository is closed, and only then.

## Native relationships

Each child is a native sub-issue of its repository-local epic. Every direct
blocker in a body's `Dependencies and blocking requirements` section is a native
`blocked_by` dependency, including cross-repository edges. Body-link text and
native state must agree, and child-level gates are never replaced with
whole-epic dependencies. A failed native write is a partial failure; there is no
body-only fallback, and the reconciler only adds relationships.

## Status labels

`status:blocked` is present on an open issue exactly when it has an open direct
blocker. `status:in-progress` does not remain on a closed issue. Older closed
issues from before Stage 21 that still carry stale labels are historical and are
reported, not changed.

## Traceability

For pack v5 the obligations are derived from the filed bodies: each acceptance
criterion and exclusion becomes `<ID>-AC-nn` or `<ID>-EX-nn`. The original
review text is not stored in either repository, and the pack says so. The
validator recomputes the expected set from the bodies.

## Procedure

```text
uv run python scripts/roadmap_sync.py reconcile           # plan only
uv run python scripts/roadmap_sync.py reconcile --apply   # idempotent
uv run python scripts/roadmap_sync.py verify              # read back
uv run python scripts/roadmap_sync.py export --state filed
uv run python scripts/check_roadmaps.py --mirror ../create-forge
```

`scripts/roadmap_sync.py` lives only in forge-template. `check_roadmaps.py`, the
label manifest and the pack are identical in both. The issue-body files are
exempt from trailing-whitespace and line-length hooks because their hard-break
spaces and long paragraphs are part of the hashed text; do not reformat them.
Pinned here by `tests/test_roadmap_packs.py`; the reconciler's tests live in forge-template.
