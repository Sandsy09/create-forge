# create-forge Roadmap Issue Index

This is the live repository-local index for the Forge Foundation roadmap,
reconciled against the v0.1.0 baseline, filed on GitHub on 2026-08-23, and
updated through #85 on 2026-08-31. GitHub issue bodies are the source of
truth for open work; completed baseline items were not backfilled as closed
issues.

| ID | GitHub issue / evidence | Status | Parent | Blocked by | Milestone |
|---|---|---|---|---|---|
| CF-00.01 | ADRs 0003 and 0006–0008 | Complete before roadmap | — | — | — |
| CF-EPIC-00 | [#33](https://github.com/Sandsy09/create-forge/issues/33) | Complete | — | — | Foundation Contract — Stage 00 |
| CF-00.02 | [#41](https://github.com/Sandsy09/create-forge/issues/41) and [ADR 0010](../../../adr/0010-public-engine-integration-contract.md) | Complete | [#33](https://github.com/Sandsy09/create-forge/issues/33) | [FT-00.02](https://github.com/Sandsy09/forge-template/issues/20) (complete), [FT-00.03](https://github.com/Sandsy09/forge-template/issues/21) (complete) | Foundation Contract — Stage 00 |
| CF-01.01 | Existing package and CLI entry point | Complete before roadmap | — | — | — |
| CF-01.02 | Existing `pyproject.toml` and uv workflow | Complete before roadmap | — | — | — |
| CF-EPIC-02 | [#34](https://github.com/Sandsy09/create-forge/issues/34) | Complete | — | — | Foundation Baseline — Stages 01–03 |
| CF-02.01 | [#42](https://github.com/Sandsy09/create-forge/issues/42) and [CLI conventions](../../../cli-conventions.md) | Complete | [#34](https://github.com/Sandsy09/create-forge/issues/34) | — | Foundation Baseline — Stages 01–03 |
| CF-02.02 | [#43](https://github.com/Sandsy09/create-forge/issues/43) and [cross-repository workflow](../../../cross-repository-workflow.md) | Complete | [#34](https://github.com/Sandsy09/create-forge/issues/34) | [#42](https://github.com/Sandsy09/create-forge/issues/42) (complete) | Foundation Baseline — Stages 01–03 |
| CF-03.01 | Existing Ruff, pytest and mypy baseline | Complete before roadmap | — | — | — |
| CF-03.02 | Existing pre-commit gate | Complete before roadmap | — | — | — |
| CF-03.03 | Existing CI and network compatibility jobs | Complete before roadmap | — | — | — |
| CF-EPIC-04 | [#35](https://github.com/Sandsy09/create-forge/issues/35) | Complete | — | — | Runtime & Security — Stages 04–05 |
| CF-04.01 | [#44](https://github.com/Sandsy09/create-forge/issues/44) and [ADR 0011](../../../adr/0011-engine-source-and-version-resolution.md) | Complete | [#35](https://github.com/Sandsy09/create-forge/issues/35) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [FT-00.03](https://github.com/Sandsy09/forge-template/issues/21) (complete) | Runtime & Security — Stages 04–05 |
| CF-EPIC-05 | [#36](https://github.com/Sandsy09/create-forge/issues/36) | Complete | — | — | Runtime & Security — Stages 04–05 |
| CF-05.01 | Existing least-privilege CI/release workflows | Complete before roadmap | — | — | — |
| CF-05.02 | [#45](https://github.com/Sandsy09/create-forge/issues/45) and [ADR 0012](../../../adr/0012-engine-dependency-update-policy.md) | Complete | [#36](https://github.com/Sandsy09/create-forge/issues/36) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [#44](https://github.com/Sandsy09/create-forge/issues/44) (complete) | Runtime & Security — Stages 04–05 |
| CF-EPIC-06 | [#37](https://github.com/Sandsy09/create-forge/issues/37), the [canonical engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md), and [engine contract tests](../../../engine-contract-tests.md) | Complete | — | — | Composition Contract — Stage 06 |
| CF-06.01 | [#46](https://github.com/Sandsy09/create-forge/issues/46) and [ADR 0013](../../../adr/0013-projectspec-construction-boundary.md) | Complete | [#37](https://github.com/Sandsy09/create-forge/issues/37) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [FT-06.01](https://github.com/Sandsy09/forge-template/issues/32) (complete), [FT-06.05](https://github.com/Sandsy09/forge-template/issues/36) (complete), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) (complete) | Composition Contract — Stage 06 |
| CF-06.02 | [#47](https://github.com/Sandsy09/create-forge/issues/47) and the [component discovery contract](../../../component-discovery.md) | Complete | [#37](https://github.com/Sandsy09/create-forge/issues/37) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [FT-06.02](https://github.com/Sandsy09/forge-template/issues/33) (complete), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) (complete) | Composition Contract — Stage 06 |
| CF-06.03 | [#48](https://github.com/Sandsy09/create-forge/issues/48) and the [engine contract tests](../../../engine-contract-tests.md) | Complete | [#37](https://github.com/Sandsy09/create-forge/issues/37) | [#46](https://github.com/Sandsy09/create-forge/issues/46) (complete), [#47](https://github.com/Sandsy09/create-forge/issues/47) (complete), [FT-06.06](https://github.com/Sandsy09/forge-template/issues/37) (complete), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) (complete) | Composition Contract — Stage 06 |
| CF-EPIC-07 | [#38](https://github.com/Sandsy09/create-forge/issues/38) | Complete | — | — | CLI Scaffolding — Stage 07 |
| CF-07.01 | [#49](https://github.com/Sandsy09/create-forge/issues/49) and [ADR 0014](../../../adr/0014-lazy-engine-reachability.md) | Complete | [#38](https://github.com/Sandsy09/create-forge/issues/38) | [#46](https://github.com/Sandsy09/create-forge/issues/46) (complete), [#47](https://github.com/Sandsy09/create-forge/issues/47) (complete), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) (complete) | CLI Scaffolding — Stage 07 |
| CF-07.02 | Existing interactive `new` flow | Complete before roadmap | — | — | — |
| CF-07.03 | Existing `--yes`/`--data` flow and tests | Complete before roadmap | — | — | — |
| CF-07.04 | [#50](https://github.com/Sandsy09/create-forge/issues/50) and [ADR 0015](../../../adr/0015-staged-filesystem-generation.md) | Complete | [#38](https://github.com/Sandsy09/create-forge/issues/38) | [#49](https://github.com/Sandsy09/create-forge/issues/49) (complete), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) (complete) | CLI Scaffolding — Stage 07 |
| CF-07.06 | [#51](https://github.com/Sandsy09/create-forge/issues/51) and [ADR 0016](../../../adr/0016-end-to-end-reference-client-tests.md) | Complete | [#38](https://github.com/Sandsy09/create-forge/issues/38) | [#49](https://github.com/Sandsy09/create-forge/issues/49) (complete), [#50](https://github.com/Sandsy09/create-forge/issues/50) (complete), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) (complete), [FT-07.05](https://github.com/Sandsy09/forge-template/issues/39) (complete) | CLI Scaffolding — Stage 07 |
| CF-EPIC-08 | [#39](https://github.com/Sandsy09/create-forge/issues/39), [ADR 0021](../../../adr/0021-client-finalises-engine-lockfiles.md), and the canonical [composition review](https://github.com/Sandsy09/forge-template/blob/main/docs/composition-architecture-review.md) | Complete | — | — | Reference Archetypes — Stage 08 |
| CF-08.01 | Existing Library registry/prompt support and the canonical [Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md) | Complete before roadmap | — | — | — |
| CF-08.02 | [#10](https://github.com/Sandsy09/create-forge/issues/10) and [ADR 0017](../../../adr/0017-cli-application-archetype-exposure.md) | Complete | [#39](https://github.com/Sandsy09/create-forge/issues/39) | [#47](https://github.com/Sandsy09/create-forge/issues/47) (complete), [forge-template#4](https://github.com/Sandsy09/forge-template/issues/4) (complete) | Reference Archetypes — Stage 08 |
| CF-08.03 | [#52](https://github.com/Sandsy09/create-forge/issues/52) and [ADR 0019](../../../adr/0019-cli-archetype-parity-review.md) | Complete | [#39](https://github.com/Sandsy09/create-forge/issues/39) | [#10](https://github.com/Sandsy09/create-forge/issues/10) (complete) | Reference Archetypes — Stage 08 |
| CF-08.04 | [#85](https://github.com/Sandsy09/create-forge/issues/85) and [ADR 0020](../../../adr/0020-engine-path-end-to-end-tests.md) | Complete | [#39](https://github.com/Sandsy09/create-forge/issues/39) | [#51](https://github.com/Sandsy09/create-forge/issues/51) (complete), [forge-template#41](https://github.com/Sandsy09/forge-template/issues/41) (complete), [#9](https://github.com/Sandsy09/create-forge/issues/9) (complete) | Reference Archetypes — Stage 08 |
| CF-EPIC-09 | [#40](https://github.com/Sandsy09/create-forge/issues/40) | Open | — | — | Blueprint Compatibility — Stage 09 |
| CF-09.01 | [#53](https://github.com/Sandsy09/create-forge/issues/53) and the canonical [organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md) | Open | [#40](https://github.com/Sandsy09/create-forge/issues/40) | [#46](https://github.com/Sandsy09/create-forge/issues/46) (complete), [FT-09.01](https://github.com/Sandsy09/forge-template/issues/44) (complete) | Blueprint Compatibility — Stage 09 |
| CF-09.02 | [#54](https://github.com/Sandsy09/create-forge/issues/54) | Blocked | [#40](https://github.com/Sandsy09/create-forge/issues/40) | [#53](https://github.com/Sandsy09/create-forge/issues/53), [FT-09.02](https://github.com/Sandsy09/forge-template/issues/45), [FT-09.04](https://github.com/Sandsy09/forge-template/issues/47) | Blueprint Compatibility — Stage 09 |
| CF-09.03 | [#55](https://github.com/Sandsy09/create-forge/issues/55) | Blocked | [#40](https://github.com/Sandsy09/create-forge/issues/40) | [#54](https://github.com/Sandsy09/create-forge/issues/54), [FT-09.05](https://github.com/Sandsy09/forge-template/issues/48) | Blueprint Compatibility — Stage 09 |

## Standalone backlog

Issues [#8](https://github.com/Sandsy09/create-forge/issues/8),
[#9](https://github.com/Sandsy09/create-forge/issues/9),
[#25](https://github.com/Sandsy09/create-forge/issues/25),
[#26](https://github.com/Sandsy09/create-forge/issues/26), and
[#91](https://github.com/Sandsy09/create-forge/issues/91) remain deliberately
outside the roadmap epics.
