# CF-EPIC-22 — Update Safety and Release Assurance

**Repository:** `create-forge`  
**Priority:** P0  
**Planning baseline:** 21 September 2026

## Outcome

Close the client-owned path-containment and recovery gaps before the next client release.

## Issue context

This work comes from the 21 September 2026 engineering review. Live reconciliation on 21 September confirms forge-template 0.6.0 is published, create-forge PR #186 is merged and CF-21.01 is closed; CF-21.02 and CF-21.03 remain open. Review observations must be rechecked against the implementation candidate.

`create-forge` owns CLI UX, ProjectSpec construction, source isolation, destination filesystem/Git/hooks and error presentation. `forge-template` owns descriptors, manifests, composition, generated content, provenance and in-memory update planning. Data flow: create-forge → ProjectSpec → forge-template discovery/render/plan → create-forge filesystem/Git finalisation.

## Problem statement

Current update.py still joins untrusted targets directly and gives one rollback hint for different Git states.

## Proposed resolution

Introduce bounded path validation, accurate recovery instructions and integrated release evidence.

## Scope

Coordinate the bounded children below. Each child owns its own implementation and evidence; this epic does not duplicate those changes.

## Acceptance criteria

- [ ] Every child below has reviewed acceptance evidence; any deferral is explicit and does not waive a release prerequisite.
- [ ] All hard dependencies are satisfied on the actual implementation/release candidate; a merged PR is not evidence of publication.
- [ ] Repository boundaries, supported compatibility and required tests are preserved.
- [ ] Tracking is reconciled with completed work; this epic closes only after all required outcomes are complete.

## Child issues

- [x] [CF-22.01](https://github.com/Sandsy09/create-forge/issues/193) — Contain all engine-update filesystem targets
- [x] [CF-22.02](https://github.com/Sandsy09/create-forge/issues/194) — Correct recovery instructions for unstaged and staged updates
- [x] [CF-22.03](https://github.com/Sandsy09/create-forge/issues/195) — Verify update safety on the final installed release candidate

## Exclusions

No unrelated features, protocol changes or repository ownership transfer. Historical ADRs remain immutable.

## Dependencies and blocking requirements

- No unresolved hard predecessor. Ready to plan; prioritisation is separate from blocking.

Use the implementation waves in the epic/roadmap to schedule work. Do not turn a preferred order into a technical blocker without a concrete reason.

## Parent epic

None; repository-owned epic.

## Tracking and roadmap

Stage 22. Existing shared labels are applied below. Stage-label/milestone and checked-in mirror synchronisation is owned by CF-24.03 and FT-24.03.

Parent/child and blocker links in this body are the filed relationship record for this batch. Native GitHub relationship fields have not been set by this filing session; do not infer native links from Markdown.

## Labels

`area:cli`, `area:tests`, `area:docs`, `area:release`, `type:epic`, `priority:critical`

## Required completion evidence

- Merged PR and exact commits, dependency versions and named check results relevant to the acceptance criteria.
- Required CONTRIBUTING checks, installed/package evidence where applicable, and updated living documentation. Add/supersede an ADR when a public boundary, dependency policy or compatibility contract changes.
- For release owners: protected CI, dry-run, immutable tag/commit, verified published wheel/sdist and applicable documentation deployment. Do not close on local-green results alone.
