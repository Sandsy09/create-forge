# Direct dependency matrix

Every direct edge is listed, including local edges for context. The verified
native GitHub blocked-by relationships are authoritative. Parent membership is
recorded separately and is not a blocked-by edge.

| Blocked issue | Blocked by | Boundary |
| --- | --- | --- |
| [FT-15.02](https://github.com/Sandsy09/forge-template/issues/147) | [FT-15.01](https://github.com/Sandsy09/forge-template/issues/146) | Local |
| [FT-15.03](https://github.com/Sandsy09/forge-template/issues/148) | [FT-15.01](https://github.com/Sandsy09/forge-template/issues/146) | Local |
| [FT-15.04](https://github.com/Sandsy09/forge-template/issues/149) | [FT-15.02](https://github.com/Sandsy09/forge-template/issues/147) | Local |
| [FT-15.04](https://github.com/Sandsy09/forge-template/issues/149) | [FT-15.03](https://github.com/Sandsy09/forge-template/issues/148) | Local |
| [CF-16.01](https://github.com/Sandsy09/create-forge/issues/155) | [FT-15.04](https://github.com/Sandsy09/forge-template/issues/149) | Cross-repo |
| [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156) | [CF-16.01](https://github.com/Sandsy09/create-forge/issues/155) | Local |
| [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) | [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156) | Local |
| [FT-17.01](https://github.com/Sandsy09/forge-template/issues/150) | [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) | Cross-repo |
| [FT-17.02](https://github.com/Sandsy09/forge-template/issues/151) | [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) | Cross-repo |
| [FT-17.03](https://github.com/Sandsy09/forge-template/issues/152) | [FT-17.02](https://github.com/Sandsy09/forge-template/issues/151) | Local |
| [FT-17.04](https://github.com/Sandsy09/forge-template/issues/153) | [FT-17.01](https://github.com/Sandsy09/forge-template/issues/150) | Local |
| [FT-17.05](https://github.com/Sandsy09/forge-template/issues/154) | [FT-17.03](https://github.com/Sandsy09/forge-template/issues/152) | Local |
| [FT-17.05](https://github.com/Sandsy09/forge-template/issues/154) | [FT-17.04](https://github.com/Sandsy09/forge-template/issues/153) | Local |
| [FT-17.06](https://github.com/Sandsy09/forge-template/issues/155) | [FT-17.05](https://github.com/Sandsy09/forge-template/issues/154) | Local |
| [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) | [FT-17.06](https://github.com/Sandsy09/forge-template/issues/155) | Cross-repo |
| [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) | [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) | Local |
| [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) | [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) | Local |
| [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) | [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) | Local |
| [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) | [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) | Local |
| [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156) | [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) | Cross-repo |
| [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156) | [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) | Cross-repo |
| [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) | [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) | Local |
| [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) | [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) | Local |
| [CF-18.07](https://github.com/Sandsy09/create-forge/issues/164) | [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156) | Cross-repo |
| [CF-18.07](https://github.com/Sandsy09/create-forge/issues/164) | [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) | Local |
| [CF-EPIC-16](https://github.com/Sandsy09/create-forge/issues/152) | [FT-15.04](https://github.com/Sandsy09/forge-template/issues/149) | Cross-repo |
| [FT-EPIC-17](https://github.com/Sandsy09/forge-template/issues/142) | [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157) | Cross-repo |
| [CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153) | [FT-17.06](https://github.com/Sandsy09/forge-template/issues/155) | Cross-repo |
| [CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153) | [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156) | Cross-repo |
| [FT-EPIC-18](https://github.com/Sandsy09/forge-template/issues/143) | [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) | Cross-repo |
| [FT-EPIC-18](https://github.com/Sandsy09/forge-template/issues/143) | [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162) | Cross-repo |

FT-15.01 is the only initially actionable child across both packs. The
Streamlit entry gate is CF-16.03; do not add CF-18.07 as a blanket blocker.
Epic blockers use boundary children, avoiding a Stage 18 parent-level cycle.
