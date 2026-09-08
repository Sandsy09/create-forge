# Direct dependency matrix

Every direct edge is listed, including local edges for context. Native GitHub
blocked-by relationships become authoritative only after filing. No issue has
been filed by this pack. Parent membership is not a blocked-by edge.

| Blocked issue | Blocked by | Boundary |
| --- | --- | --- |
| [FT-15.02](forge-template/FT-15.02.md) | [FT-15.01](forge-template/FT-15.01.md) | Local |
| [FT-15.03](forge-template/FT-15.03.md) | [FT-15.01](forge-template/FT-15.01.md) | Local |
| [FT-15.04](forge-template/FT-15.04.md) | [FT-15.02](forge-template/FT-15.02.md) | Local |
| [FT-15.04](forge-template/FT-15.04.md) | [FT-15.03](forge-template/FT-15.03.md) | Local |
| [CF-16.01](create-forge/CF-16.01.md) | [FT-15.04](forge-template/FT-15.04.md) | Cross-repo |
| [CF-16.02](create-forge/CF-16.02.md) | [CF-16.01](create-forge/CF-16.01.md) | Local |
| [CF-16.03](create-forge/CF-16.03.md) | [CF-16.02](create-forge/CF-16.02.md) | Local |
| [FT-17.01](forge-template/FT-17.01.md) | [CF-16.03](create-forge/CF-16.03.md) | Cross-repo |
| [FT-17.02](forge-template/FT-17.02.md) | [CF-16.03](create-forge/CF-16.03.md) | Cross-repo |
| [FT-17.03](forge-template/FT-17.03.md) | [FT-17.02](forge-template/FT-17.02.md) | Local |
| [FT-17.04](forge-template/FT-17.04.md) | [FT-17.01](forge-template/FT-17.01.md) | Local |
| [FT-17.05](forge-template/FT-17.05.md) | [FT-17.03](forge-template/FT-17.03.md) | Local |
| [FT-17.05](forge-template/FT-17.05.md) | [FT-17.04](forge-template/FT-17.04.md) | Local |
| [FT-17.06](forge-template/FT-17.06.md) | [FT-17.05](forge-template/FT-17.05.md) | Local |
| [CF-18.01](create-forge/CF-18.01.md) | [FT-17.06](forge-template/FT-17.06.md) | Cross-repo |
| [CF-18.02](create-forge/CF-18.02.md) | [CF-18.01](create-forge/CF-18.01.md) | Local |
| [CF-18.03](create-forge/CF-18.03.md) | [CF-18.01](create-forge/CF-18.01.md) | Local |
| [CF-18.04](create-forge/CF-18.04.md) | [CF-18.03](create-forge/CF-18.03.md) | Local |
| [CF-18.05](create-forge/CF-18.05.md) | [CF-18.04](create-forge/CF-18.04.md) | Local |
| [FT-18.01](forge-template/FT-18.01.md) | [CF-18.02](create-forge/CF-18.02.md) | Cross-repo |
| [FT-18.01](forge-template/FT-18.01.md) | [CF-18.05](create-forge/CF-18.05.md) | Cross-repo |
| [CF-18.06](create-forge/CF-18.06.md) | [CF-18.02](create-forge/CF-18.02.md) | Local |
| [CF-18.06](create-forge/CF-18.06.md) | [CF-18.05](create-forge/CF-18.05.md) | Local |
| [CF-18.07](create-forge/CF-18.07.md) | [FT-18.01](forge-template/FT-18.01.md) | Cross-repo |
| [CF-18.07](create-forge/CF-18.07.md) | [CF-18.06](create-forge/CF-18.06.md) | Local |
| [CF-EPIC-16](create-forge/CF-EPIC-16.md) | [FT-15.04](forge-template/FT-15.04.md) | Cross-repo |
| [FT-EPIC-17](forge-template/FT-EPIC-17.md) | [CF-16.03](create-forge/CF-16.03.md) | Cross-repo |
| [CF-EPIC-18](create-forge/CF-EPIC-18.md) | [FT-17.06](forge-template/FT-17.06.md) | Cross-repo |
| [CF-EPIC-18](create-forge/CF-EPIC-18.md) | [FT-18.01](forge-template/FT-18.01.md) | Cross-repo |
| [FT-EPIC-18](forge-template/FT-EPIC-18.md) | [CF-18.02](create-forge/CF-18.02.md) | Cross-repo |
| [FT-EPIC-18](forge-template/FT-EPIC-18.md) | [CF-18.05](create-forge/CF-18.05.md) | Cross-repo |

FT-15.01 is the only initially actionable child across both packs. The
Streamlit entry gate is CF-16.03; do not add CF-18.07 as a blanket blocker.
Epic blockers use boundary children, avoiding a Stage 18 parent-level cycle.
