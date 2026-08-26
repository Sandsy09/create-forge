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
- [x] [**CF-04.01 — Define template-engine source and version resolution**](https://github.com/Sandsy09/create-forge/issues/44)
  ([ADR 0011](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0011-engine-source-and-version-resolution.md),
  [canonical engine resolution contract](https://github.com/Sandsy09/create-forge/blob/main/docs/engine-resolution.md))

## Stage record

The completed forge-template FT-04.01 through FT-04.05 decisions keep runtime
configuration, environment inputs, event vocabularies, paths, resources, and
exceptions owner-local. They assign assembly and process-wide logging
configuration to the runtime entrypoint without adding Foundation runtime
code, a path helper, or a universal exception hierarchy. They change no CLI
behaviour: create-forge's current `FORGE_*` variables, filesystem orchestration,
and user-facing diagnostics remain CLI-local, while `forge-template` owns the
corresponding generated-project conventions.

CF-04.01 closes the create-forge side of the stage: ADR 0011 defines how a
released CLI obtains the `forge-template` engine (a bounded, install-time
dependency; channel deferred to CF-05.02), the explicit
`--engine-source`/`--engine-ref` local-development override that replaces
`--template-url` only at the coordinated cutover, the diagnostics contract
`create-forge doctor`/`doctor --json` now implement, and the reserved exit
status `3` for a future unsupported engine or ProjectSpec protocol. No engine
package exists yet, so no version range is assigned — `templates.toml`,
`--template-url`, and `--ref` are unchanged in v0.1.x.

The create-forge epic ([CF-EPIC-04 / #35](https://github.com/Sandsy09/create-forge/issues/35))
is complete. `forge-template`'s Stage 04 counterpart
([FT-EPIC-04 / #13](https://github.com/Sandsy09/forge-template/issues/13))
already has all five of its children closed; closing it is that repository's
own call.

## Stage completion rule

- [x] Repo-local issues are complete or explicitly deferred.
- [x] Cross-repository blockers are resolved.
- [x] Public contracts changed by this stage are documented/versioned.
- [x] No implementation concern is duplicated across repositories.
