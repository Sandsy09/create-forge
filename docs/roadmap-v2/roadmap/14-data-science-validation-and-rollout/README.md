# Stage 14 — Data Science Validation and Rollout

## Epics

- [FT-EPIC-14 / forge-template#99](https://github.com/Sandsy09/forge-template/issues/99)
  reviews composition and publishes the reviewed engine line.
- [CF-EPIC-14 / create-forge#104](https://github.com/Sandsy09/create-forge/issues/104)
  adopts that release and completes real client validation.

## Dependencies

FT-EPIC-14 is natively blocked by CF-EPIC-13. CF-EPIC-14 is natively blocked
by FT-EPIC-14, enforcing provider review and release before client adoption.

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
`--engine-preview`, all epics and their later children are complete, and the
cross-repository graph and documentation describe the shipped state.

## Non-goals

No default engine cutover, plugin system, policy resolver, deployment
platform, or unrelated archetype is introduced.
