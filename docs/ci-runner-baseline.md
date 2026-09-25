# CI runner baseline

This is the living contract for which GitHub-hosted runner images
`create-forge`'s workflows run on, how the next Ubuntu image is trialled, and
when it is promoted. [ADR 0058](adr/0058-pin-the-ubuntu-runner-baseline-with-a-canary.md)
records the decision; `scripts/check_workflows.py` and
`tests/test_workflows.py` enforce the parts a CI edit could silently break.

## Why it matters

`ubuntu-latest` is an alias GitHub repoints on its own schedule. Left in place,
the effective Linux baseline changes without a reviewed commit, and the first
sign is a red protected check. The
[17 September 2026 announcement](https://github.blog/changelog/2026-09-17-ubuntu-26-generally-available-and-latest-migration/)
([runner-images #14747](https://github.com/actions/runner-images/issues/14747),
[#14748](https://github.com/actions/runner-images/issues/14748)) says
`ubuntu-latest` moves from Ubuntu 24.04 to **26.04**, rolling out gradually
between **19 October and 19 November 2026**, and that the move "may break
builds" relying on tools that changed between the images. The review-reported
19 October date is the start of that window, not a single cut-over day.

## Current labels

The `Baseline` and `Canary` rows are read by `tests/test_workflows.py`, which
fails if the workflows disagree with them.

| Role | Label | Runs |
| --- | --- | --- |
| Baseline | `ubuntu-24.04` | every protected Ubuntu job: the `linux` call in `ci.yml`, its `all-green` aggregate, and every job in `docs.yml` and `release.yml` |
| Canary | `ubuntu-26.04` | the identical Linux checks, in `runner-canary.yml`, non-blocking |
| Unpinned | `windows-latest` | the three Windows jobs in `ci.yml`; a known gap, see below |

Pinning is per image, so it still receives GitHub's routine image updates
(a new `20260920.314.1`-style version of the same OS). What it removes is the
*OS* moving under a merge.

## How the pieces fit

- `linux-checks.yml` is a reusable workflow (`workflow_call`, one required
  `runner` input) holding the Linux jobs: documentation, lint, the Python
  3.11–3.14 test matrix, wheel contents, the dependency floor, network tests
  and end-to-end generation. It has read-only permissions and the same SHA
  pins as every other workflow.
- `ci.yml` calls it once with the baseline label. The required aggregate
  `All checks passed` needs that call and the Windows jobs.
- `runner-canary.yml` calls it once with the canary label, on the same triggers
  as CI (push to `main`, pull requests, the Monday cron, manual dispatch). It
  has no aggregate job and nothing depends on it, so it cannot block a merge and
  cannot produce the required check's name.

Because the two callers share one definition, the canary cannot drift from the
protected checks: what is proven on 26.04 is exactly what is required on 24.04.

`release.yml` and `docs.yml` hold release-capable scopes (`contents: write`,
`id-token: write`, `pages: write`), so they are pinned to the baseline and are
deliberately not canaried; the checks that protect a release are the ones in
the canary's scope.

## Ownership

The repository maintainer owns the canary ([CODEOWNERS](../.github/CODEOWNERS)).
A red canary is triaged within one week of the first failing run, by one of:

1. fixing the code or test so it works on both images;
2. filing an `area:ci` issue that names the failing job and the image
   difference, when the fix is larger than the change that surfaced it.

An open canary-attributed issue blocks promotion.

## Promotion

The baseline moves to the canary's image when **all** of these hold:

- the canary is green on `main` HEAD;
- the canary is green on each of the four most recent Monday scheduled runs
  (the cron exercises `network` and `e2e` against whatever `forge-template`
  currently publishes);
- no canary-attributed issue is open;
- the canary's `e2e`, `network` and `wheel` jobs — the installed-package,
  engine/legacy generation and update, Git-lifecycle and generated-project
  evidence — are among the runs counted, not merely lint.

Promotion is one pull request that changes the label everywhere it is named:
`ci.yml`'s `linux` call and `all-green`, every job in `docs.yml` and
`release.yml`, the `Baseline` row above, and the Linux row of
[engine-cutover-acceptance.md](engine-cutover-acceptance.md). The canary is then
pointed at the next candidate image, or kept on the old baseline as a rollback
lane. A promotion needs no new ADR while it follows these criteria; changing the
criteria, or dropping the canary, does.

If GitHub announces a deprecation or brownout schedule for the baseline image,
promotion moves ahead of it regardless of the four-run window.

## Rollback

Every label is explicit, so rolling back is reverting the promotion pull
request. Nothing else moves: the canary lane is the previous baseline until it
is retired.

## Known gap: `windows-latest`

The Windows jobs still use the moving alias (today the image reports
`windows-2025-vs2026`). The baseline decision was scoped to Ubuntu, and a
tracked follow-up pins it. `check_workflows.py` rejects `ubuntu-latest` only;
it does not yet reject `windows-latest`. Whoever pins Windows extends that check
and this document in the same change.

## Evidence

Recorded for CF-24.01 ([#198](https://github.com/Sandsy09/create-forge/issues/198)).

### Inventory before the change

Image observed in `main` run 35789169581 (22 September 2026), all resolved from
`ubuntu-latest` unless noted.

| Workflow | Jobs | Label | Resolved image |
| --- | --- | --- | --- |
| `ci.yml` | `docs`, `lint`, `test` ×4, `wheel`, `floor`, `network`, `e2e`, `all-green` | `ubuntu-latest` | `ubuntu-24.04`, version `20260907.300.1`–`20260920.314.1` |
| `ci.yml` | `windows`, `e2e-windows`, `e2e-windows-encoding` ×3 | `windows-latest` | `windows-2025-vs2026` |
| `docs.yml` | `build`, `deploy` | `ubuntu-latest` | `ubuntu-24.04` |
| `release.yml` | `release`, `publish` | `ubuntu-latest` | `ubuntu-24.04` |

### Validation of this change

Pull request [#223](https://github.com/Sandsy09/create-forge/pull/223), head
commit `eb5daad`. The image each job reports in its "Set up job" log:

| Run | Workflow | Image | Version | Result |
| --- | --- | --- | --- | --- |
| [36195927931](https://github.com/Sandsy09/create-forge/actions/runs/36195927931) | `ci.yml`, baseline | `ubuntu-24.04` | `20260920.314.1` | all 10 Linux jobs and `All checks passed` green |
| [36195927931](https://github.com/Sandsy09/create-forge/actions/runs/36195927931) | `ci.yml`, Windows | `windows-2025-vs2026` | `20260922.246.2` | all 5 Windows jobs green |
| [36195927745](https://github.com/Sandsy09/create-forge/actions/runs/36195927745) | `runner-canary.yml` | `ubuntu-26.04` | `20260920.143.1` | all 10 Linux jobs green |

The canary ran the whole client validation set on 26.04, not a subset: the
installed-package and install-mode paths, engine and legacy generation and
update, the Git lifecycle and generated-project checks (`End-to-end generation`,
7m10s), the real `update()` against released tags (`Network tests`), the
dependency floor, the wheel-contents check, the documentation build, and the
full Python 3.11–3.14 matrix. The Windows-only installed-update-safety and
encoding jobs are unchanged and stay on the protected gate.

**One observation, not a finding:** a single green run is not the promotion
evidence. Promotion needs the four scheduled Monday runs above, so this run
proves the canary works and 26.04 is viable today, and starts the count.

**Guard evidence:** reintroducing `ubuntu-latest` into `docs.yml` locally
failed `test_real_workflows_have_no_errors`, `test_runner_labels_pass_on_real_set`
and `test_protected_ubuntu_jobs_run_on_the_contract_baseline`; restoring it
passed.
