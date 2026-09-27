# Stages 22 to 29 roadmap

## Status

Filed and open. This pack records 10 repository-owned epics and 27 children
(18 issues in forge-template, 19 in create-forge) for Stages 22–29, with
verified issue numbers, labels, milestones, native parents and direct
dependencies. No release or runtime implementation is claimed by these
planning documents.

Earlier packs ([roadmap-v3](../roadmap-v3/README.md) and
[roadmap-v4](../roadmap-v4/README.md)) stay frozen exactly as filed. This pack
adds Stages 22–29 beside them and never edits their bodies or hashes.

## Read this pack

- [Stage overview, proposed waves and status snapshot](ROADMAP.md)
- [Obligation traceability](TRACEABILITY.md)
- [GitHub filing record and reconciliation procedure](github-issues/GITHUB-SETUP.md)
- [Direct dependency matrix](github-issues/CROSS-REPO-DEPENDENCIES.md)
- [Client issue index](github-issues/create-forge/ISSUE-INDEX.md)
- [Provider issue index](github-issues/forge-template/ISSUE-INDEX.md)
- [Machine-readable filing manifest](github-issues/filing-manifest.json)
- [Living tracking conventions](../roadmap-tracking.md)

## Coordination

The pack is mirrored byte-for-byte in both repositories. GitHub bodies and
native relationships are authoritative; the pack records the filed text and
the graph. Live open/closed state and `status:*` labels are not frozen here
because they change; only the dated snapshot in [ROADMAP.md](ROADMAP.md)
mentions them and is regenerated.

## Validation

From either repository root:

```text
uv run python scripts/check_roadmaps.py
uv run python scripts/check_roadmaps.py --mirror ../create-forge
```

The provider repository additionally owns `scripts/roadmap_sync.py`
(`export`, `reconcile`, `verify`); see
[GITHUB-SETUP.md](github-issues/GITHUB-SETUP.md).
