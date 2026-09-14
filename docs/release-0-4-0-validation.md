# create-forge 0.4.0 Release Validation

This is the living evidence record for
[CF-18.07 / #164](https://github.com/Sandsy09/create-forge/issues/164), the
seventh and last child of
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153): it
publishes create-forge `0.4.0`, verifies the released `create-forge` /
`forge-template 0.5.0` pair against its own artefacts, and closes the
Engine-Default Cutover roadmap. The decision is accepted under
[ADR 0049](adr/0049-publish-0-4-0-and-close-roadmap-v3.md).

`0.4.0` is the cutover release: the `forge-template` engine is the default,
required `new` architecture; `copier` is the optional `legacy` extra; the
removed `--engine-preview` flag no longer exists. It is a **breaking**
release — the default `new` behaviour and the resolved dependency set both
change from `0.3.x`.

**Publication status: not yet published.** This record's identity, published
verification, and roadmap reconciliation sections are filled in only after
the real `release.yml` dispatch and the published-artefact audit run —
CONTRIBUTING forbids a success claim based on local-green tests alone. Until
then the sections below are placeholders naming what each will contain.

## Release identity

*Pending — filled in after `release.yml` publishes.*

| Field | Value |
| --- | --- |
| Tag | |
| Source commit | |
| GitHub release | |
| PyPI project | |
| wheel | |
| sdist | |

## Compatibility

- **Default path is the engine.** `create-forge new` discovers the catalogue
  from `forge_template.get_engine_info()`, constructs a ProjectSpec, and
  renders through its public facade — no template repository to clone.
- **`forge-template>=0.5,<0.6`** is a required dependency of plain
  `create-forge`, not an extra. `copier<10,>=9.16` moved to the optional
  `legacy` extra (`create-forge[legacy]`).
- Against `forge-template 0.5.0`, engine discovery returns the `library`,
  `cli`, and `data-science` archetypes and the `jupyter` and
  `scientific-python` capabilities.
- `create-forge 0.3.x` remains installable and supported for at least 90 days
  and at least one further tagged release past this publication
  (`docs/engine-cutover-acceptance.md § Rollback and support windows`).

## Published-artefact verification

*Pending — every command below will run against the **published** `0.4.0`,
not a local build, in throwaway virtual environments, matching the depth of
[docs/release-0-3-0-validation.md](release-0-3-0-validation.md)'s seven
checks.*

### 1. Tag, release, and source commit agree

### 2. PyPI artefacts and dependency metadata

`requires_dist` must show `forge-template>=0.5,<0.6` as a plain dependency
and `copier<10,>=9.16` carrying `extra == "legacy"`.

### 3. `templates.toml` ships in the published wheel

### 4. The four contractual install modes

`uvx create-forge==0.4.0`, `uv tool install create-forge==0.4.0`,
`pip install create-forge==0.4.0`, and `create-forge[legacy]==0.4.0`, each
running `--version`, `list`, and `doctor --json` — confirming
`integration.line == "v0.4.x-engine"` and
`integration.engine_package == "0.5.0"`.

### 5. Engine generation of every archetype

`library`, `cli`, and `data-science --capability jupyter`, each with the
generated project's own `uv run --locked poe check`, plus `.forge/generation.json`,
`uv.lock`, and the initial Git commit.

### 6. The `--legacy` Copier route and an engine-native update round-trip

### 7. `uvx`, and the `0.3.2` pin-back

`uvx --from "create-forge==0.4.0"`, and
`uv tool install "create-forge==0.3.2"` still resolving, installing, and
generating — the support-window row the acceptance contract promises.

Plus the documentation-deployment check AC-03 names: `docs.yml` green on the
release commit, and a live fetch of the guide index, `installation/`,
`updates/`, and `migration/` pages.

## Roadmap reconciliation

*Pending.*

The Engine-Default Cutover roadmap is 5 epics and 21 children across two
repositories, plus the shared review obligations
[CF-ROADMAP-01-AC-06](roadmap-v3/TRACEABILITY.md) and
[CF-ROADMAP-01-AC-07](roadmap-v3/TRACEABILITY.md). At `0.4.0` this section
will record which have landed evidence and are closed, in the same shape
[docs/release-0-3-0-validation.md § Roadmap
reconciliation](release-0-3-0-validation.md#roadmap-reconciliation) closed
roadmap-v2.

### CF-EPIC-18 acceptance

| Criterion | Discharged by |
| --- | --- |
| The engine is the default, required `new` path; `copier` is the optional `legacy` extra | ADR 0040; CF-18.01 |
| `--engine-source`/`--engine-ref` provision an isolated environment | ADR 0044; CF-18.02 |
| The engine `new` Git/hook lifecycle and `.forge/generation.json` | ADR 0045; CF-18.03 |
| Engine-native `update` dispatch | ADR 0046; CF-18.04 |
| The legacy Copier route and preview-project transition | ADR 0047; CF-18.05 |
| The installed-console acceptance matrix and rewritten user guide | ADR 0048; CF-18.06 |
| Publication, verification, and roadmap close-out | this record; CF-18.07 |

`docs/roadmap-v3/github-issues/filing-manifest.json`, the 24 filed issue
bodies, and `scripts/check_roadmaps.py` stay unchanged by this closure — the
checker has no "complete" pack status, so completion is recorded here and in
the roadmap-v3 Status prose instead, matching ADR 0049 decision 5.

## Boundaries retained

No shipped module, dependency range, CLI flag, protocol, component
identifier, or default path changes in this release beyond what CF-18.01–
CF-18.06 already merged to `main`. `create-forge 0.4.0` is the release that
publishes them.

When a later create-forge release is published, add its own record rather
than editing this one.
