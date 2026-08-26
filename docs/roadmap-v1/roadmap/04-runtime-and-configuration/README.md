# Stage 04 — Runtime and Configuration

## Repository ownership

### forge-template

- [x] [**FT-04.01 — Define configuration ownership and extension conventions**](https://github.com/Sandsy09/forge-template/issues/24)
  ([canonical conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/configuration-ownership.md),
  [ADR 0015](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0015-owner-local-runtime-configuration.md))
- [x] [**FT-04.02 — Define environment-variable conventions**](https://github.com/Sandsy09/forge-template/issues/25)
  ([canonical conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/environment-variables.md),
  [ADR 0016](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0016-owner-local-environment-inputs.md))
- **FT-04.03 — Define structured logging baseline**
- **FT-04.04 — Define path and resource handling conventions**
- **FT-04.05 — Define exception conventions**

### create-forge

- Epic: [CF-EPIC-04 / #35](https://github.com/Sandsy09/create-forge/issues/35)
- [**CF-04.01 — Define template-engine source and version resolution**](https://github.com/Sandsy09/create-forge/issues/44)

## Stage record

The completed forge-template FT-04.01 and FT-04.02 decisions keep runtime
configuration and environment inputs owner-local, explicitly assembled, and
provider-neutral. They change no CLI behaviour: create-forge's current
`FORGE_*` variables remain CLI-local configuration, while `forge-template`
owns generated-project schemas, validation, and environment conventions.

## Stage completion rule

- [ ] Repo-local issues are complete or explicitly deferred.
- [ ] Cross-repository blockers are resolved.
- [ ] Public contracts changed by this stage are documented/versioned.
- [ ] No implementation concern is duplicated across repositories.
