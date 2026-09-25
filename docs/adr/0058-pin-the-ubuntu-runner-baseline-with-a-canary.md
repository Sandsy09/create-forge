# 58. Pin the Ubuntu runner baseline and trial the next image with a canary

## Status

Accepted

## Context

[Issue #198 / CF-24.01](https://github.com/Sandsy09/create-forge/issues/198),
the first child of
[CF-EPIC-24](https://github.com/Sandsy09/create-forge/issues/190), reports an
`ubuntu-latest` migration to Ubuntu 26.04 beginning 19 October 2026. Every
Ubuntu job in `ci.yml`, `docs.yml` and `release.yml` used `runs-on:
ubuntu-latest`, so the effective baseline was implicit.

The review's observation was rechecked against primary sources rather than
taken as written. GitHub's
[17 September 2026 changelog](https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/)
and [actions/runner-images #14747](https://github.com/actions/runner-images/issues/14747)/[#14748](https://github.com/actions/runner-images/issues/14748)
confirm: `ubuntu-26.04` (x64 and arm64) is generally available, and
`ubuntu-latest` migrates from 24.04 to 26.04 *gradually between 19 October and
19 November 2026*. The 19 October date is therefore the start of a month-long
window, not a cut-over day, and the announcement itself warns the move may break
workflows that depend on tools that changed. The image every job resolves to
today is `ubuntu-24.04` (image version `20260920.314.1` in the latest `main` run
at the time of writing), and `windows-latest` resolves to `windows-2025-vs2026`.

Two constraints shape the decision. Branch protection requires exactly one
check, `All checks passed`, and that must stay the single gate. And the
repository's workflow-security contract (ADR 0037) requires SHA-pinned actions
and least-privilege permissions, which any new workflow must also satisfy.

## Decision

1. **The supported Linux baseline is explicit: `ubuntu-24.04`.** Every
   protected Ubuntu job names it, in `ci.yml`, `docs.yml` and `release.yml`.
   `ubuntu-latest` is forbidden; `scripts/check_workflows.py` rejects it,
   including as the `runner` input passed to a reusable workflow.
2. **The Linux checks are one reusable workflow, `linux-checks.yml`,** taking
   the runner label as a required input. `ci.yml` calls it with the baseline;
   the required aggregate depends on that call.
3. **A non-blocking canary runs the identical checks on `ubuntu-26.04`,**
   in its own workflow, `runner-canary.yml`, on the same triggers as CI. It has
   no aggregate job and nothing depends on it, so it cannot block a merge or
   produce the required check's name. `tests/test_workflows.py` asserts both.
4. **The baseline, the canary, ownership, promotion and rollback criteria are
   a living contract,** [docs/ci-runner-baseline.md](../ci-runner-baseline.md).
   A promotion that follows those criteria is one pull request changing the
   label everywhere it is named; it does not need a new ADR. Changing the
   criteria, or retiring the canary, does.
5. **`windows-latest` is out of scope.** The issue is about the Ubuntu
   migration. It is recorded in the contract as a known, unpinned alias and
   tracked as a follow-up rather than silently left.
6. **`release.yml` and `docs.yml` are pinned but not canaried.** They hold
   release-capable scopes; the checks that protect a release are exactly what
   the canary already runs.

## Consequences

- The Linux OS no longer changes under a merge. It changes in a reviewed pull
  request, after the canary has produced evidence.
- The canary cannot drift from the gate, because both call one definition;
  promotion is a one-string change plus the contract.
- **A job cannot depend on a job inside a called workflow.** The three Windows
  jobs previously waited on `lint`; they now run concurrently with it, so a
  formatting slip no longer short-circuits them. This costs some Windows
  runner minutes on a lint failure and nothing else.
- Check names in the pull-request UI gain a prefix
  (`Linux (ubuntu-24.04) / Lint`). Only `All checks passed` is required, so
  branch protection is unaffected.
- One more workflow file, and a second full run of the Linux suite per push,
  pull request and Monday cron. The repository is public, so the minutes are
  free.
- An accepted gap: the Windows runner image is still an alias that can move.
  Closing it needs its own image-identity check (the plain `windows-2025` label
  is not assumed to be the image `windows-latest` resolves to) and is tracked
  separately.
- Historical ADRs that name `ubuntu-latest` (0016, 0042) describe
  what was true when written and are not edited.
