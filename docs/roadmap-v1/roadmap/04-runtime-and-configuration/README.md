# Stage 04 — Runtime and Configuration

## Repository ownership

### forge-template

- [x] [**FT-04.01 — Define configuration ownership and extension conventions**](https://github.com/Sandsy09/forge-template/issues/24)
  ([canonical conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/configuration-ownership.md),
  [ADR 0015](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0015-owner-local-runtime-configuration.md))
- [x] [**FT-04.02 — Define environment-variable conventions**](https://github.com/Sandsy09/forge-template/issues/25)
  ([canonical conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/environment-variables.md),
  [ADR 0016](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0016-owner-local-environment-inputs.md))
- [x] [**FT-04.03 — Define structured logging capability**](https://github.com/Sandsy09/forge-template/issues/26)
  ([canonical contract](https://github.com/Sandsy09/forge-template/blob/main/docs/structured-logging.md),
  [ADR 0017](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0017-owner-local-structured-logging.md))
- [x] [**FT-04.04 — Define path and resource ownership conventions**](https://github.com/Sandsy09/forge-template/issues/27)
  ([canonical conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/paths-and-resources.md),
  [ADR 0018](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0018-owner-local-paths-and-resources.md))
- [x] [**FT-04.05 — Define exception ownership conventions**](https://github.com/Sandsy09/forge-template/issues/28)
  ([canonical conventions](https://github.com/Sandsy09/forge-template/blob/main/docs/exception-ownership.md),
  [ADR 0019](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0019-owner-local-exceptions.md))

### create-forge

- Epic: [CF-EPIC-04 / #35](https://github.com/Sandsy09/create-forge/issues/35)
- [**CF-04.01 — Define template-engine source and version resolution**](https://github.com/Sandsy09/create-forge/issues/44)

## Stage record

The completed forge-template FT-04.01 through FT-04.05 decisions keep runtime
configuration, environment inputs, event vocabularies, paths, resources, and
exceptions owner-local. They assign assembly and process-wide logging
configuration to the runtime entrypoint without adding Foundation runtime
code, a path helper, or a universal exception hierarchy. They change no CLI
behaviour: create-forge's current `FORGE_*` variables, filesystem orchestration,
and user-facing diagnostics remain CLI-local, while `forge-template` owns the
corresponding generated-project conventions.

## Stage completion rule

- [ ] Repo-local issues are complete or explicitly deferred.
- [ ] Cross-repository blockers are resolved.
- [ ] Public contracts changed by this stage are documented/versioned.
- [ ] No implementation concern is duplicated across repositories.
