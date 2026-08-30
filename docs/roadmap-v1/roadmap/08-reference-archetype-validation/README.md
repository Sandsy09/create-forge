# Stage 08 — Reference Archetype Validation

## Repository ownership

### forge-template

- ~~**FT-08.01 — Define Library archetype contract**~~ — complete via the
  [canonical contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md),
  [ADR 0031](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0031-library-archetype-contract.md),
  and [forge-template PR #79](https://github.com/Sandsy09/forge-template/pull/79).
- ~~**FT-08.02 — Migrate the Library archetype to the composition contract**~~
  — complete via [forge-template PR #81](https://github.com/Sandsy09/forge-template/pull/81).
- ~~**FT-08.03 — Select and define the second reference archetype contract**~~
  — CLI Application selected via the
  [canonical contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md),
  [ADR 0034](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0034-select-cli-application-reference-archetype.md),
  and [forge-template PR #82](https://github.com/Sandsy09/forge-template/pull/82).
- ~~**FT-08.04 — Implement the CLI Application reference archetype**~~ —
  complete via
  [forge-template PR #84](https://github.com/Sandsy09/forge-template/pull/84),
  released at `forge-template` `0.3.0` alongside Library.
- **FT-08.05 — Run composition architecture review**

### create-forge

- Epic: [CF-EPIC-08 / #39](https://github.com/Sandsy09/create-forge/issues/39)
- ~~**CF-08.01 — Expose Library archetype through create-forge**~~ — completed before roadmap filing.
- ~~**CF-08.02 — Expose CLI Application through create-forge**~~ — complete via
  [ADR 0017](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0017-cli-application-archetype-exposure.md),
  which moves this repository's exact development pin to `forge-template==0.3.0`
  and adds a discovery-driven `--archetype` option and prompt behind
  `--engine-preview`.
- [**CF-08.03 — Run CLI archetype-parity review**](https://github.com/Sandsy09/create-forge/issues/52)
  — unblocked now that CF-08.02 is complete.
- [**CF-08.04 — Extend end-to-end generation to the public engine**](https://github.com/Sandsy09/create-forge/issues/85)
  — successor to [CF-07.06 / #51](https://github.com/Sandsy09/create-forge/issues/51).
  Its production-catalogue acceptance criterion is now met by CF-08.02; the
  remaining one needs a *released, range-assigned* engine, blocked on
  [#9](https://github.com/Sandsy09/create-forge/issues/9) alone.

The Library decision records the legacy answer mapping into
`component_options.library.packaging_mode`; CF-08.02 wires it on the engine
path via `spec.legacy_library_answers` and
`engine.map_legacy_library_options`. CLI Application is selected as
engine-owned ID `cli`, has no component options, and derives its console
command from `ProjectSpec.project.repository_name`; FT-08.04 implemented it
and create-forge #10 exposes it, both landing in this stage.

## Stage completion rule

- [ ] Repo-local issues are complete or explicitly deferred.
- [ ] Cross-repository blockers are resolved.
- [ ] Public contracts changed by this stage are documented/versioned.
- [ ] No implementation concern is duplicated across repositories.
