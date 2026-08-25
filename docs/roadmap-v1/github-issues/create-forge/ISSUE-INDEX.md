# create-forge Roadmap Issue Index

This is the live repository-local index for the Forge Foundation roadmap,
reconciled against the v0.1.0 baseline, filed on GitHub on 2026-08-23, and
updated through CF-02.02 on 2026-08-25. GitHub issue bodies are the source of
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
| CF-EPIC-04 | [#35](https://github.com/Sandsy09/create-forge/issues/35) | Open | — | — | Runtime & Security — Stages 04–05 |
| CF-04.01 | [#44](https://github.com/Sandsy09/create-forge/issues/44) | Open | [#35](https://github.com/Sandsy09/create-forge/issues/35) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [FT-00.03](https://github.com/Sandsy09/forge-template/issues/21) (complete) | Runtime & Security — Stages 04–05 |
| CF-EPIC-05 | [#36](https://github.com/Sandsy09/create-forge/issues/36) | Blocked | — | — | Runtime & Security — Stages 04–05 |
| CF-05.01 | Existing least-privilege CI/release workflows | Complete before roadmap | — | — | — |
| CF-05.02 | [#45](https://github.com/Sandsy09/create-forge/issues/45) | Blocked | [#36](https://github.com/Sandsy09/create-forge/issues/36) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [#44](https://github.com/Sandsy09/create-forge/issues/44) | Runtime & Security — Stages 04–05 |
| CF-EPIC-06 | [#37](https://github.com/Sandsy09/create-forge/issues/37) | Blocked | — | — | Composition Contract — Stage 06 |
| CF-06.01 | [#46](https://github.com/Sandsy09/create-forge/issues/46) | Blocked | [#37](https://github.com/Sandsy09/create-forge/issues/37) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [FT-06.01](https://github.com/Sandsy09/forge-template/issues/32), [FT-06.05](https://github.com/Sandsy09/forge-template/issues/36), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) | Composition Contract — Stage 06 |
| CF-06.02 | [#47](https://github.com/Sandsy09/create-forge/issues/47) | Blocked | [#37](https://github.com/Sandsy09/create-forge/issues/37) | [#41](https://github.com/Sandsy09/create-forge/issues/41) (complete), [FT-06.02](https://github.com/Sandsy09/forge-template/issues/33), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) | Composition Contract — Stage 06 |
| CF-06.03 | [#48](https://github.com/Sandsy09/create-forge/issues/48) | Blocked | [#37](https://github.com/Sandsy09/create-forge/issues/37) | [#46](https://github.com/Sandsy09/create-forge/issues/46), [#47](https://github.com/Sandsy09/create-forge/issues/47), [FT-06.06](https://github.com/Sandsy09/forge-template/issues/37), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) | Composition Contract — Stage 06 |
| CF-EPIC-07 | [#38](https://github.com/Sandsy09/create-forge/issues/38) | Blocked | — | — | CLI Scaffolding — Stage 07 |
| CF-07.01 | [#49](https://github.com/Sandsy09/create-forge/issues/49) | Blocked | [#38](https://github.com/Sandsy09/create-forge/issues/38) | [#46](https://github.com/Sandsy09/create-forge/issues/46), [#47](https://github.com/Sandsy09/create-forge/issues/47), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) | CLI Scaffolding — Stage 07 |
| CF-07.02 | Existing interactive `new` flow | Complete before roadmap | — | — | — |
| CF-07.03 | Existing `--yes`/`--data` flow and tests | Complete before roadmap | — | — | — |
| CF-07.04 | [#50](https://github.com/Sandsy09/create-forge/issues/50) | Blocked | [#38](https://github.com/Sandsy09/create-forge/issues/38) | [#49](https://github.com/Sandsy09/create-forge/issues/49), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38) | CLI Scaffolding — Stage 07 |
| CF-07.06 | [#51](https://github.com/Sandsy09/create-forge/issues/51) | Blocked | [#38](https://github.com/Sandsy09/create-forge/issues/38) | [#49](https://github.com/Sandsy09/create-forge/issues/49), [#50](https://github.com/Sandsy09/create-forge/issues/50), [FT-06.07](https://github.com/Sandsy09/forge-template/issues/38), [FT-07.05](https://github.com/Sandsy09/forge-template/issues/39) | CLI Scaffolding — Stage 07 |
| CF-EPIC-08 | [#39](https://github.com/Sandsy09/create-forge/issues/39) | Blocked | — | — | Reference Archetypes — Stage 08 |
| CF-08.01 | Existing Library registry/prompt support | Complete before roadmap | — | — | — |
| CF-08.02 | [#10](https://github.com/Sandsy09/create-forge/issues/10) | Blocked | [#39](https://github.com/Sandsy09/create-forge/issues/39) | [#47](https://github.com/Sandsy09/create-forge/issues/47), [forge-template#4](https://github.com/Sandsy09/forge-template/issues/4) | Reference Archetypes — Stage 08 |
| CF-08.03 | [#52](https://github.com/Sandsy09/create-forge/issues/52) | Blocked | [#39](https://github.com/Sandsy09/create-forge/issues/39) | [#10](https://github.com/Sandsy09/create-forge/issues/10) | Reference Archetypes — Stage 08 |
| CF-EPIC-09 | [#40](https://github.com/Sandsy09/create-forge/issues/40) | Blocked | — | — | Blueprint Compatibility — Stage 09 |
| CF-09.01 | [#53](https://github.com/Sandsy09/create-forge/issues/53) | Blocked | [#40](https://github.com/Sandsy09/create-forge/issues/40) | [#46](https://github.com/Sandsy09/create-forge/issues/46), [FT-09.01](https://github.com/Sandsy09/forge-template/issues/44) | Blueprint Compatibility — Stage 09 |
| CF-09.02 | [#54](https://github.com/Sandsy09/create-forge/issues/54) | Blocked | [#40](https://github.com/Sandsy09/create-forge/issues/40) | [#53](https://github.com/Sandsy09/create-forge/issues/53), [FT-09.02](https://github.com/Sandsy09/forge-template/issues/45), [FT-09.04](https://github.com/Sandsy09/forge-template/issues/47) | Blueprint Compatibility — Stage 09 |
| CF-09.03 | [#55](https://github.com/Sandsy09/create-forge/issues/55) | Blocked | [#40](https://github.com/Sandsy09/create-forge/issues/40) | [#54](https://github.com/Sandsy09/create-forge/issues/54), [FT-09.05](https://github.com/Sandsy09/forge-template/issues/48) | Blueprint Compatibility — Stage 09 |

## Standalone backlog

Issues [#8](https://github.com/Sandsy09/create-forge/issues/8),
[#9](https://github.com/Sandsy09/create-forge/issues/9),
[#25](https://github.com/Sandsy09/create-forge/issues/25), and
[#26](https://github.com/Sandsy09/create-forge/issues/26) remain deliberately
outside the roadmap epics.
