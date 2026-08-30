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
- ~~**CF-08.03 — Run CLI archetype-parity review**~~ — complete via
  [ADR 0019](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0019-cli-archetype-parity-review.md)
  and [create-forge#52](https://github.com/Sandsy09/create-forge/issues/52).
  The shared ProjectSpec/pipeline path and engine-owned discovery were
  confirmed generic; the one archetype-specific branch found
  (`pipeline._resolved_component_options`) is now gated by a discovered
  descriptor rather than a hardcoded archetype id. The engine path's
  Library-shaped prompt set was recorded, not fixed, and tracked by
  [create-forge#91](https://github.com/Sandsy09/create-forge/issues/91).
- ~~**CF-08.04 — Extend end-to-end generation to the public engine**~~ —
  complete via
  [ADR 0020](https://github.com/Sandsy09/create-forge/blob/main/docs/adr/0020-engine-path-end-to-end-tests.md)
  and [create-forge#85](https://github.com/Sandsy09/create-forge/issues/85),
  successor to [CF-07.06 / #51](https://github.com/Sandsy09/create-forge/issues/51).
  `tests/test_e2e_engine_generation.py` generates both archetypes through
  `--engine-preview` against the real installed engine, runs each generated
  project's own checks, and proves the released-install compatibility
  boundary (an out-of-range engine installed from a git tag, and no `engine`
  extra at all) writes nothing. This closes
  [CF-EPIC-08 / #39](https://github.com/Sandsy09/create-forge/issues/39).

The Library decision records the legacy answer mapping into
`component_options.library.packaging_mode`; CF-08.02 wires it on the engine
path via `spec.legacy_library_answers` and
`engine.map_legacy_library_options`. CLI Application is selected as
engine-owned ID `cli`, has no component options, and derives its console
command from `ProjectSpec.project.repository_name`; FT-08.04 implemented it
and create-forge #10 exposes it, both landing in this stage.

All four `create-forge`-repo-local issues (CF-08.01 through CF-08.04) are
complete, and CF-EPIC-08 / #39 is closed. This stage's `forge-template`-side
item, FT-08.05 ("Run composition architecture review"), remains open
independently in that repository -- Stage 08 as a whole stays open on this
document until it closes too.

## Stage completion rule

- [ ] Repo-local issues are complete or explicitly deferred. -- true for
  `create-forge` (CF-08.01 through CF-08.04); `forge-template`'s FT-08.05 is
  still open.
- [x] Cross-repository blockers are resolved. -- #9/ADR 0018 was the last one.
- [x] Public contracts changed by this stage are documented/versioned --
  ADR 0017, ADR 0019, ADR 0020, and the canonical docs they reference.
- [x] No implementation concern is duplicated across repositories -- CF-08.03
  (ADR 0019) confirmed this directly.
