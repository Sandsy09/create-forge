# Stage 14 — Data Science Validation and Rollout

## Epics

- [FT-EPIC-14 / forge-template#99](https://github.com/Sandsy09/forge-template/issues/99)
  reviews composition and publishes the reviewed engine line.
- [CF-EPIC-14 / create-forge#104](https://github.com/Sandsy09/create-forge/issues/104)
  adopts that release and completes real client validation.

## Dependencies

FT-EPIC-14 is natively blocked by CF-EPIC-13. CF-EPIC-14 is natively blocked
by FT-EPIC-14, enforcing provider review and release before client adoption.
Both provider blockers are complete. CF-14.01 adopts the resulting
`forge-template 0.4.1` release under
[ADR 0031](../../../adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md),
and CF-14.02 validates both accepted Data Science compositions through the
installed create-forge candidate under
[ADR 0032](../../../adr/0032-validate-installed-data-science-generation.md).
CF-14.03 is the remaining open validation step; CF-14.04 stays blocked on it.

## Child sequence

forge-template completes provider review first:

1. [FT-14.01 / #113](https://github.com/Sandsy09/forge-template/issues/113)
   reviews and corrects three-archetype composition boundaries after CF-13.05.
2. [FT-14.02 / #114](https://github.com/Sandsy09/forge-template/issues/114)
   runs cross-repository compatibility validation against both main branches.
3. [FT-14.03 / #115](https://github.com/Sandsy09/forge-template/issues/115)
   publishes and verifies the reviewed `forge-template` 0.4.1 release.

create-forge then completes client rollout:

1. [CF-14.01 / create-forge#111](https://github.com/Sandsy09/create-forge/issues/111)
   adopts the reviewed 0.4.1 engine release (complete; ADR 0031).
2. [CF-14.02 / create-forge#112](https://github.com/Sandsy09/create-forge/issues/112)
   runs installed-console Data Science end-to-end validation. **Complete**
   under
   [ADR 0032](../../../adr/0032-validate-installed-data-science-generation.md):
   the `0.3.0` candidate wheel and published `forge-template 0.4.1` pair
   generate both accepted compositions deterministically, pass locked checks
   and notebooks across the Python handoff matrix, build clean distributions,
   and install without Forge runtime dependencies.
3. [CF-14.03 / create-forge#113](https://github.com/Sandsy09/create-forge/issues/113)
   completes existing-path regressions and failure validation.
4. [CF-14.04 / create-forge#114](https://github.com/Sandsy09/create-forge/issues/114)
   publishes create-forge 0.3.0 and completes roadmap v2; it remains blocked
   only by CF-14.03.

## Entry criteria

- create-forge Stage 13 exercises the full Data Science composition.
- All three archetypes and the selected capabilities have executable evidence.

## Outcomes

- Review ownership, duplication, extension points, compatibility, security,
  reproducibility, package size, and maintenance cost.
- Correct any Foundation or component boundary defects.
- Publish and verify the reviewed forge-template release.
- Adopt its compatible range in create-forge.
- Generate Data Science through the real console script, verify its lock, and
  run its canonical checks and notebook validation.
- Re-run Library, CLI Application, and Copier-path regressions.
- Publish any required create-forge release and close the roadmap milestones.

## Exit criteria

The released client and engine pair supports Data Science behind
`--engine-preview`, all epics and their children are complete, and the
cross-repository graph and documentation describe the shipped state.

## Non-goals

No default engine cutover, plugin system, policy resolver, deployment
platform, or unrelated archetype is introduced.
