# Canonical contracts

This is the index of `create-forge`'s living contract documents — the
`docs/*.md` files that fix behaviour a test or an ADR treats as binding, as
opposed to prose that merely describes the code. [CLAUDE.md](../CLAUDE.md) and
[CONTRIBUTING.md](../CONTRIBUTING.md) point here rather than restating this
list; several entries have their own link-audit test in
[tests/test_engine_contract.py](../tests/test_engine_contract.py) or
[tests/test_reference_client_boundary.py](../tests/test_reference_client_boundary.py)
requiring them to stay linked from here.

A contract changes in the same pull request as the behaviour it describes.
Records are living documents, not immutable like an ADR — but a change to one
still usually cites the ADR that authorised it.

## CLI surface

| Contract | Governs |
| --- | --- |
| [cli-conventions.md](cli-conventions.md) | Input precedence, prompt-skipping, interactive/non-interactive parity, validation ownership, exit statuses. |
| [component-selection.md](component-selection.md) | `--capability`/`--platform`/`--component-option` flags, absent-vs-explicit-empty, precedence, prompt order (ADR 0027). |
| [engine-default-cli.md](engine-default-cli.md) | The post-cutover command surface: engine as the default `new` path, `--legacy`, `--engine-source`/`--engine-ref` (ADR 0040). |
| [engine-project-lifecycle.md](engine-project-lifecycle.md) | Post-generation `git init`/commit/hooks, `.forge/generation.json`, and `update` dispatch (ADR 0041). |
| [engine-cutover-acceptance.md](engine-cutover-acceptance.md) | The cutover release, supported OS/Python/install matrix, acceptance gates, support and deprecation windows (ADR 0042). |

## Engine boundary

| Contract | Governs |
| --- | --- |
| [integration-contract.md](integration-contract.md) | The evolving package/protocol compatibility rules with `forge-template` (ADR 0010). Its compatibility table is asserted byte-exact by a test. |
| [engine-resolution.md](engine-resolution.md) | How the engine package is sourced, overridden locally, diagnosed, and rejected when incompatible (ADR 0011). |
| [engine-updates.md](engine-updates.md) | How a compatibility-line dependency bump is adopted, how a breaking line is crossed, and what Dependabot may never do alone (ADR 0012). |
| [project-spec-construction.md](project-spec-construction.md) | The CLI-answer-to-ProjectSpec field mapping and validation `spec.py`/`engine.py` implement (ADR 0013). |
| [component-discovery.md](component-discovery.md) | Protocol negotiation, descriptor ownership, and the no-fallback trust boundary in `engine.py`. |
| [engine-contract-tests.md](engine-contract-tests.md) | The supported package/protocol range and the sibling-checkout contract-test command. |
| [downstream-client-reference.md](downstream-client-reference.md) | `examples/downstream_cli.py` — a second, independent client proving no `create-forge` dependency is required (ADR 0023). |
| [organisation-policy-consumption.md](organisation-policy-consumption.md) | The `SelectionRequest`/`SelectionProvenance` seam, and why `create-forge` ships no policy parser (ADR 0022). |

## Filesystem and tests

| Contract | Governs |
| --- | --- |
| [filesystem-generation.md](filesystem-generation.md) | Destination-conflict, staging, finalisation, and cleanup rules in `staging.py` (ADR 0015), and the shared target-safety boundary in `paths.py` that both generation and engine-native `update` resolve every engine-supplied path through (ADR 0052). |
| [end-to-end-tests.md](end-to-end-tests.md) | The fast/`network`/`e2e` test-tier split and what the real console script is proven to do (ADR 0016). |

## Validation records

Acceptance-checklist-to-named-test maps, each closing an epic or a release.

| Contract | Governs |
| --- | --- |
| [data-science-preview-validation.md](data-science-preview-validation.md) | CF-EPIC-13's acceptance checklist against the Data Science preview pipeline (ADR 0030). |
| [installed-data-science-validation.md](installed-data-science-validation.md) | Both Data Science compositions through the installed candidate wheel (ADR 0032). |
| [rollout-regression-validation.md](rollout-regression-validation.md) | Library/CLI Application engine paths, the engine-less default, and the full selection/option/destination/lock/cleanup failure matrix (ADR 0033). |
| [release-0-3-0-validation.md](release-0-3-0-validation.md) | The published `create-forge 0.3.0` / `forge-template 0.4.1` pair verified against its own artefacts (ADR 0034). |
| [engine-cutover-validation.md](engine-cutover-validation.md) | The installed-console cutover acceptance matrix's remaining rows, and the rewritten user guide (ADR 0048). |
| [release-0-4-0-validation.md](release-0-4-0-validation.md) | The published `create-forge 0.4.0` / `forge-template 0.5.0` pair verified against its own artefacts, and the Engine-Default Cutover roadmap close-out (ADR 0049). |
| [installed-streamlit-validation.md](installed-streamlit-validation.md) | The four accepted Streamlit compositions, the previous-line provider, and the Streamlit failure cases through the installed candidate wheel (ADR 0051). |
| [subprocess-output.md](subprocess-output.md) | How every process the client starts is captured as bytes and decoded by an explicit rule (diagnostic, protocol, path/binary), the site inventory, the worker's UTF-8 wire format, and the test-harness rule (ADR 0055). |
| [update-safety-validation.md](update-safety-validation.md) | Update containment and recovery proven through the installed candidate wheel, the candidate's hashes and safety-relevant source digest, and CF-21.03's release prerequisite (ADR 0054). |

## Process and security

| Contract | Governs |
| --- | --- |
| [workflow-security.md](workflow-security.md) | SHA-pinning external Actions and per-job `permissions:` scoping (ADR 0037). |
| [cross-repository-workflow.md](cross-repository-workflow.md) | Validating sibling `create-forge`/`forge-template` checkouts before merge or release. |
| [ADR 0024](adr/0024-reference-client-not-framework-dependency.md) | `create-forge` is one reference client, not a framework dependency for the engine or generated projects. |
| [ADR 0037](adr/0037-immutable-workflow-actions.md) | The SHA-pinning and permissions rule `workflow-security.md` records. |

## Elsewhere

- [docs/adr/README.md](adr/README.md) — the full Architecture Decision Record
  index, in Nygard format.
- [docs/roadmap-v1/](roadmap-v1/) through [docs/roadmap-v4/](roadmap-v4/) —
  completed and in-flight cross-repository roadmaps.
- [docs/user-guide/](user-guide/) — the published
  [Forge user guide](https://sandsy09.github.io/create-forge/) (end-user
  docs; source of `reference.md`'s own technical-reference index for engine
  APIs hosted in `forge-template`).
