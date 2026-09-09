# Direct dependency matrix

Every direct edge is listed, including local edges for context. The verified
native GitHub blocked-by relationships are authoritative. Parent membership is
recorded separately and is not a blocked-by edge.

| Blocked issue | Blocked by | Boundary |
| --- | --- | --- |
| [FT-19.01](https://github.com/Sandsy09/forge-template/issues/157) | [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) | Cross-repo |
| [FT-19.02](https://github.com/Sandsy09/forge-template/issues/158) | [FT-19.01](https://github.com/Sandsy09/forge-template/issues/157) | Local |
| [FT-20.01](https://github.com/Sandsy09/forge-template/issues/159) | [FT-19.02](https://github.com/Sandsy09/forge-template/issues/158) | Local |
| [FT-20.02](https://github.com/Sandsy09/forge-template/issues/160) | [FT-20.01](https://github.com/Sandsy09/forge-template/issues/159) | Local |
| [FT-20.03](https://github.com/Sandsy09/forge-template/issues/161) | [FT-20.02](https://github.com/Sandsy09/forge-template/issues/160) | Local |
| [FT-20.04](https://github.com/Sandsy09/forge-template/issues/162) | [FT-20.03](https://github.com/Sandsy09/forge-template/issues/161) | Local |
| [CF-21.01](https://github.com/Sandsy09/create-forge/issues/165) | [FT-20.04](https://github.com/Sandsy09/forge-template/issues/162) | Cross-repo |
| [CF-21.02](https://github.com/Sandsy09/create-forge/issues/166) | [CF-21.01](https://github.com/Sandsy09/create-forge/issues/165) | Local |
| [CF-21.03](https://github.com/Sandsy09/create-forge/issues/167) | [CF-21.02](https://github.com/Sandsy09/create-forge/issues/166) | Local |
| [FT-EPIC-19](https://github.com/Sandsy09/forge-template/issues/144) | [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) | Cross-repo |
| [FT-EPIC-20](https://github.com/Sandsy09/forge-template/issues/145) | [FT-19.02](https://github.com/Sandsy09/forge-template/issues/158) | Local |
| [CF-EPIC-21](https://github.com/Sandsy09/create-forge/issues/154) | [FT-20.04](https://github.com/Sandsy09/forge-template/issues/162) | Cross-repo |

FT-15.01 is the only initially actionable child across both packs. The
Streamlit entry gate is CF-16.03; do not add CF-18.07 as a blanket blocker.
Epic blockers use boundary children, avoiding a Stage 18 parent-level cycle.
