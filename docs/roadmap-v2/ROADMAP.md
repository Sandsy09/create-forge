# Data Science Roadmap

The roadmap is one product sequence split across two repositories. A stage
gets a repository-local epic only where that repository owns unfinished work.

| Stage | Theme | forge-template epic | create-forge epic |
| --- | --- | --- | --- |
| 10 | Data Science Architecture Contract | [#96 / FT-EPIC-10](https://github.com/Sandsy09/forge-template/issues/96) | — |
| 11 | Reusable Data Science Capabilities | [#97 / FT-EPIC-11](https://github.com/Sandsy09/forge-template/issues/97) | — |
| 12 | Data Science Archetype | [#98 / FT-EPIC-12](https://github.com/Sandsy09/forge-template/issues/98) | — |
| 13 | Data Science CLI Integration | — | [#103 / CF-EPIC-13](https://github.com/Sandsy09/create-forge/issues/103) |
| 14 | Validation and Rollout | [#99 / FT-EPIC-14](https://github.com/Sandsy09/forge-template/issues/99) | [#104 / CF-EPIC-14](https://github.com/Sandsy09/create-forge/issues/104) |

## Delivery order

```text
FT-EPIC-10
    ↓
FT-EPIC-11
    ↓
FT-EPIC-12 ──────────────┐
                         ↓
create-forge#91 ───→ CF-EPIC-13
                         ↓
                    FT-EPIC-14
                         ↓
                    CF-EPIC-14
```

Completed `create-forge#91` is retained as a native predecessor because its
engine-native option prompting is required before an option-bearing component
composition can be presented generically.

## Delivery rules

- All 24 child issues are filed and attached to their native epics.
- Implement children in dependency order without reopening accepted Stage 10
  decisions in downstream delivery work.
- Child issues live in the repository that owns their implementation.
- Native GitHub `blocked by` relationships are authoritative.
- Provider changes merge and release from forge-template before create-forge
  adopts the released compatibility line.
- The direct-Copier Library path remains supported and unchanged throughout
  this roadmap.
