# Streamlit Archetype roadmap

## Status

Prepared, not filed. This pack contains 3 repository-owned epics and
9 child drafts for Stages 19–21. No issue numbers, milestones,
releases or implementation are claimed by these documents.

Streamlit begins after the provider and client cutover contracts are accepted.
If cutover has not shipped, client adoption uses the supported engine-preview
path without expanding the Copier registry or changing plain installs.

## Read this pack

- [Stage overview](ROADMAP.md)
- [Architecture and decision boundaries](ARCHITECTURE.md)
- [Repository ownership](REPOSITORY-OWNERSHIP.md)
- [Review traceability](TRACEABILITY.md)
- [GitHub setup and future filing procedure](github-issues/GITHUB-SETUP.md)
- [Direct dependency matrix](github-issues/CROSS-REPO-DEPENDENCIES.md)
- [Client issue index](github-issues/create-forge/ISSUE-INDEX.md)
- [Provider issue index](github-issues/forge-template/ISSUE-INDEX.md)
- [Machine-readable filing manifest](github-issues/filing-manifest.json)

## Coordination

The two packs are mirrored in both repositories. Before filing, the reviewed
manifest and complete bodies are the proposed source of truth. After filing,
GitHub bodies and native relationships are authoritative; update both mirrors
when decisions alter scope or dependencies. Never invent GitHub numbers.

The companion [Engine-Default Cutover roadmap](../roadmap-v3/README.md) shares
the contract gates. Preserve completed roadmap-v1/v2 records and historical
ADRs.

## Preparation validation

From either repository root:

```bash
uv run python scripts/check_roadmaps.py
uv run poe check
uv run pre-commit run --all-files
```

For a normal sibling layout, compare from create-forge with
`uv run python scripts/check_roadmaps.py --mirror ../forge-template`,
or from forge-template with
`uv run python scripts/check_roadmaps.py --mirror ../create-forge`.
Use an absolute mirror path when reviewing an isolated worktree.
The checker reads both packs, validates links/anchors and the filing graph,
and compares mirrored bytes and shared label manifests when requested.
It performs no GitHub writes. The create-forge shared guide also requires
`uv run poe docs:build`; provider technical docs are not a MkDocs site.
