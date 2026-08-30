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
- [**FT-08.04 — Implement the CLI Application reference archetype**](https://github.com/Sandsy09/forge-template/issues/4)
- **FT-08.05 — Run composition architecture review**

### create-forge

- Epic: [CF-EPIC-08 / #39](https://github.com/Sandsy09/create-forge/issues/39)
- ~~**CF-08.01 — Expose Library archetype through create-forge**~~ — completed before roadmap filing.
- [**CF-08.02 — Expose CLI Application through create-forge**](https://github.com/Sandsy09/create-forge/issues/10)
- [**CF-08.03 — Run CLI archetype-parity review**](https://github.com/Sandsy09/create-forge/issues/52)
- [**CF-08.04 — Extend end-to-end generation to the public engine**](https://github.com/Sandsy09/create-forge/issues/85)
  — successor to [CF-07.06 / #51](https://github.com/Sandsy09/create-forge/issues/51),
  carrying forward the two acceptance criteria that need a released engine and
  a non-empty production catalogue. FT-08.02 is complete on
  `forge-template/main`; [#9](https://github.com/Sandsy09/create-forge/issues/9)
  remains its only open native blocker.

The Library decision records the legacy answer mapping into
`component_options.library.packaging_mode`, but no create-forge code, exact
development pin, released engine range, or protocol-support claim changes in
this documentation handoff. CLI Application is now selected as engine-owned
ID `cli`, has no component options, and derives its console command from
`ProjectSpec.project.repository_name`; FT-08.04 owns implementation and
create-forge #10 owns its later exposure.

## Stage completion rule

- [ ] Repo-local issues are complete or explicitly deferred.
- [ ] Cross-repository blockers are resolved.
- [ ] Public contracts changed by this stage are documented/versioned.
- [ ] No implementation concern is duplicated across repositories.
