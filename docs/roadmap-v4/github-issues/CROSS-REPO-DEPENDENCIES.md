# Direct dependency matrix

Every direct edge is listed, including local edges for context. Native GitHub
blocked-by relationships become authoritative only after filing. No issue has
been filed by this pack. Parent membership is not a blocked-by edge.

| Blocked issue | Blocked by | Boundary |
| --- | --- | --- |
| [FT-19.01](forge-template/FT-19.01.md) | [CF-16.03](../../roadmap-v3/github-issues/create-forge/CF-16.03.md) | Cross-repo |
| [FT-19.02](forge-template/FT-19.02.md) | [FT-19.01](forge-template/FT-19.01.md) | Local |
| [FT-20.01](forge-template/FT-20.01.md) | [FT-19.02](forge-template/FT-19.02.md) | Local |
| [FT-20.02](forge-template/FT-20.02.md) | [FT-20.01](forge-template/FT-20.01.md) | Local |
| [FT-20.03](forge-template/FT-20.03.md) | [FT-20.02](forge-template/FT-20.02.md) | Local |
| [FT-20.04](forge-template/FT-20.04.md) | [FT-20.03](forge-template/FT-20.03.md) | Local |
| [CF-21.01](create-forge/CF-21.01.md) | [FT-20.04](forge-template/FT-20.04.md) | Cross-repo |
| [CF-21.02](create-forge/CF-21.02.md) | [CF-21.01](create-forge/CF-21.01.md) | Local |
| [CF-21.03](create-forge/CF-21.03.md) | [CF-21.02](create-forge/CF-21.02.md) | Local |
| [FT-EPIC-19](forge-template/FT-EPIC-19.md) | [CF-16.03](../../roadmap-v3/github-issues/create-forge/CF-16.03.md) | Cross-repo |
| [FT-EPIC-20](forge-template/FT-EPIC-20.md) | [FT-19.02](forge-template/FT-19.02.md) | Local |
| [CF-EPIC-21](create-forge/CF-EPIC-21.md) | [FT-20.04](forge-template/FT-20.04.md) | Cross-repo |

FT-15.01 is the only initially actionable child across both packs. The
Streamlit entry gate is CF-16.03; do not add CF-18.07 as a blanket blocker.
Epic blockers use boundary children, avoiding a Stage 18 parent-level cycle.
