# Engine-Default Cutover roadmap

## Status

Prepared, not filed. This pack contains 5 repository-owned epics and
21 child drafts for Stages 15–18. No issue numbers, milestones,
releases or implementation are claimed by these documents.

Working engine-native updates and continued support for existing Copier
projects gate the engine-default release. Detailed architecture remains
subject to the explicit decision children.

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

The next [Streamlit roadmap](../roadmap-v4/README.md) shares the contract
gates. Preserve completed roadmap-v1/v2 records and historical ADRs.

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
