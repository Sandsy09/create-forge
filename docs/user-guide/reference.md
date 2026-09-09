# Reference and project direction

The user guides describe released behaviour. The repositories retain
detailed contracts, implementation evidence, and architectural decisions
for contributors and people building on the engine.

## Build your own engine client

`forge-template` is also a Python package with a public API for component
discovery, validation, planning, and in-memory rendering:

```bash
uv add "forge-template==0.4.1"
```

Add it to the project implementing your client. It is not a required
dependency of projects generated with the CLI. Start with the
[public engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
and the runnable
[downstream client example](https://github.com/Sandsy09/create-forge/blob/main/examples/README.md).
Your client owns filesystem writes and command execution; the engine
returns validated content in memory.

Organisation defaults and constraints can be resolved by a downstream
client before calling the engine. `create-forge` itself does not load
organisation policy files, and the engine does not support arbitrary
file-overlay or plugin directories.

## Technical reference index

| Topic | Source |
| --- | --- |
| CLI input and prompting | [CLI conventions](https://github.com/Sandsy09/create-forge/blob/main/docs/cli-conventions.md) |
| Engine selection and options | [Component selection](https://github.com/Sandsy09/create-forge/blob/main/docs/component-selection.md) |
| Engine package compatibility | [Engine resolution](https://github.com/Sandsy09/create-forge/blob/main/docs/engine-resolution.md) |
| Generation requests | [ProjectSpec](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md) |
| Catalogue metadata | [Component manifests](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md) |
| Organisation clients | [Policy and constraints](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md) |
| Independent clients | [Reference client boundary](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0024-reference-client-not-framework-dependency.md) |
| Shared generated tooling | [Foundation guarantees](https://github.com/Sandsy09/forge-template/blob/main/docs/foundation-guarantees.md) |
| Working across repositories | [Contributor workflow](https://github.com/Sandsy09/create-forge/blob/main/docs/cross-repository-workflow.md) |
| Why decisions were made | [CLI ADRs](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/README.md), [template ADRs](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/README.md) |

Technical documents on `main` may describe accepted future contracts. Check
their status sections before treating an interface as a released feature.

## What's next

The Foundation and Data Science roadmaps are complete. The current release
keeps Copier as the default and exposes the engine through an opt-in
preview. Making the engine the default is a planned direction, with no
scheduled release or supported migration available yet.

Prepared roadmap packs now outline the
[Engine-Default Cutover](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v3/README.md)
and [Streamlit Archetype](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v4/README.md).
These are unfiled plans, not available features. Engine-native updates and
continued legacy Copier updates must work before the default switch.
Streamlit can proceed after the cutover contracts are accepted; adoption stays
on the supported preview path if the cutover has not shipped.

Follow [CLI open work](https://github.com/Sandsy09/create-forge/issues),
[template open work](https://github.com/Sandsy09/forge-template/issues), and
the [CLI](https://github.com/Sandsy09/create-forge/releases) and
[template](https://github.com/Sandsy09/forge-template/releases) releases.
The completed
[Foundation](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v1/README.md)
and [Data Science](https://github.com/Sandsy09/create-forge/blob/main/docs/roadmap-v2/README.md)
roadmaps remain available as historical records.

[Suggest a capability or guide](feedback.md) to help shape future work.
