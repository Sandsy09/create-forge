# Engine-Default Cutover roadmap

## Status

Filed and delivered. This pack recorded 5 repository-owned epics and
21 children for Stages 15–18, with verified issue numbers, labels,
milestones, native parents and direct dependencies. The filed manifest, the
issue bodies, and `scripts/check_roadmaps.py`'s expected output stay
unchanged (`filed-open`) by design — completion is recorded in prose here
and in the evidence record below, not in the pack's own filing status; see
ADR 0049 decision 5.

The engine-default cutover this pack planned has shipped:
[FT-18.01](https://github.com/Sandsy09/forge-template/issues/156) closed the
provider-side integrated validation, and CF-18.07
([#164](https://github.com/Sandsy09/create-forge/issues/164), ADR 0049)
published it as **`create-forge 0.4.0`**. See
`docs/release-0-4-0-validation.md` for the full publication evidence and
roadmap reconciliation.

Working engine-native updates and continued support for existing Copier
projects gated the engine-default release; both shipped.

## Read this pack

- [Stage overview](ROADMAP.md)
- [Architecture and decision boundaries](ARCHITECTURE.md)
- [Repository ownership](REPOSITORY-OWNERSHIP.md)
- [Review traceability](TRACEABILITY.md)
- [GitHub filing record and reconciliation procedure](github-issues/GITHUB-SETUP.md)
- [Direct dependency matrix](github-issues/CROSS-REPO-DEPENDENCIES.md)
- [Client issue index](github-issues/create-forge/ISSUE-INDEX.md)
- [Provider issue index](github-issues/forge-template/ISSUE-INDEX.md)
- [Machine-readable filing manifest](github-issues/filing-manifest.json)

## Coordination

The two packs are mirrored in both repositories. The reviewed manifest and
complete bodies record the filed state. GitHub bodies and native relationships
are authoritative; update both mirrors when decisions alter scope or
dependencies. Never invent or reuse GitHub numbers.

The next [Streamlit roadmap](../roadmap-v4/README.md) shares the contract
gates. Preserve completed roadmap-v1/v2 records and historical ADRs.

## Filed-state validation

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
