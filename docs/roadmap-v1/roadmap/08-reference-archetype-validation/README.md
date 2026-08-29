# Stage 08 — Reference Archetype Validation

## Repository ownership

### forge-template

- ~~**FT-08.01 — Define Library archetype contract**~~ — complete via the
  [canonical contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md),
  [ADR 0031](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0031-library-archetype-contract.md),
  and [forge-template PR #79](https://github.com/Sandsy09/forge-template/pull/79).
- **FT-08.02 — Migrate the Library archetype to the composition contract**
- **FT-08.03 — Select and define the second reference archetype contract**
- **FT-08.04 — Implement the selected second reference archetype**
- **FT-08.05 — Run composition architecture review**

### create-forge

- Epic: [CF-EPIC-08 / #39](https://github.com/Sandsy09/create-forge/issues/39)
- ~~**CF-08.01 — Expose Library archetype through create-forge**~~ — completed before roadmap filing.
- [**CF-08.02 — Expose a second archetype through create-forge**](https://github.com/Sandsy09/create-forge/issues/10)
- [**CF-08.03 — Run CLI archetype-parity review**](https://github.com/Sandsy09/create-forge/issues/52)
- [**CF-08.04 — Extend end-to-end generation to the public engine**](https://github.com/Sandsy09/create-forge/issues/85)
  — successor to [CF-07.06 / #51](https://github.com/Sandsy09/create-forge/issues/51),
  carrying forward the two acceptance criteria that need a released engine and
  a non-empty production catalogue, neither of which exists yet. Blocked on
  [FT-08.02 / forge-template#41](https://github.com/Sandsy09/forge-template/issues/41)
  and [#9](https://github.com/Sandsy09/create-forge/issues/9).

The Library decision records the legacy answer mapping into
`component_options.library.packaging_mode`, but no create-forge code, exact
development pin, released engine range, or protocol-support claim changes in
this documentation handoff. The second archetype remains deliberately unnamed
until FT-08.03 selects it.

## Stage completion rule

- [ ] Repo-local issues are complete or explicitly deferred.
- [ ] Cross-repository blockers are resolved.
- [ ] Public contracts changed by this stage are documented/versioned.
- [ ] No implementation concern is duplicated across repositories.
