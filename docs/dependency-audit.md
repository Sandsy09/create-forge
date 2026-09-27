# Dependency vulnerability audit

This is the canonical living contract for auditing `create-forge`'s **own
resolved dependencies** for known vulnerabilities. [ADR
0059](adr/0059-audit-resolved-dependencies-with-uv-audit.md) records the
decision. `scripts/audit_dependencies.py` implements it and
`tests/test_dependency_audit.py` pins it.

A clean audit is not a claim that the dependencies are secure. It says only
that no advisory in the queried database matched a locked version, at the
time of the query.

## What is audited

The audit reads `uv.lock` and reports three scopes separately, each derived
from `pyproject.toml` rather than hardcoded, so a new dependency group or
extra narrows the right scope automatically:

| Scope | What it is | Packages (2026-09-27) |
| --- | --- | --- |
| `runtime` | `[project.dependencies]` and everything they lock: the graph the published wheel depends on, including `forge-template` itself. Findings here are provider-actionable and start the lower-bound review below. | 22 |
| `legacy` | `runtime` plus the `legacy` extra (`copier`, `platformdirs`, and what they bring in). Also provider-actionable. | 29 |
| `full` | Every extra and every dependency group (`docs`, `lint`, `test`, `typecheck`, `dev`). The additions beyond `runtime`/`legacy` are development-only. | 73 |

A finding is attributed to the **narrowest** scope that contains it: a
finding also present in `runtime` is reported once, as `[runtime]`, not
three times. A finding only ever present in `full` is labelled `[full]` --
it never reaches a consumer, but it still fails the audit (the user's
deliberate choice: a vulnerable CI tool is still a vulnerable tool sitting in
the lock).

**Not audited here:** dependencies rendered into a generated project (each
project scans its own graph), pre-commit hook revisions (manual, [issue
#17](https://github.com/Sandsy09/create-forge/issues/17)), and GitHub Actions
(the separate SHA-pinning rule -- [workflow security
contract](workflow-security.md), [ADR 0037](adr/0037-immutable-workflow-actions.md)).

## Scanner and coverage

The scanner is `uv audit` (preview), which resolves `uv.lock` and queries
[OSV](https://osv.dev). CI pins `UV_VERSION` exactly, so the interface a run
sees is the interface the tests were written against; both `0.12.0` (the pin)
and `0.12.5` were verified against this repository's own lock.

- **Python and platform markers.** `uv.lock` is universal, so the audit
  covers every package the lock can install on any Python `>=3.11` and any
  platform the lock resolves for -- including a marker-gated package such as
  `colorama` (Windows only). It does not audit a single interpreter's
  installed environment.
- **A fresh `uvx create-forge` install is not covered.** The audit reads this
  repository's own `uv.lock`; a consumer's resolver can still pick a
  different, newer version within the declared ranges. Dependabot's weekly
  lock refresh keeps that gap narrow, and a `[runtime]`/`[legacy]` finding
  triggers the lower-bound review, which is the mechanism that actually
  changes what a consumer can install.
- **Advisory data version.** OSV is queried live and has no snapshot version,
  so a run cannot be reproduced later. Each run therefore records the scanner
  version (`uv --version`), the UTC query time, and, for every finding, the
  advisory's own `modified` timestamp. The job log and step summary are the
  evidence.
- **No credential-bearing output.** The script strips `scheme://user:pass@`
  and query strings from anything it echoes, including a connection-failure
  message that names a URL.

### Why the scope is derived and cross-checked

`uv audit --no-default-groups` and `--only-dev` are **silently ineffective**
(verified on uv `0.12.0` and `0.12.5` against this lock): both still audit the
full 68/73-package graph. Only `--no-group <name>` and `--no-extra <name>`
narrow it reliably, and `uv audit` audits **every extra by default** --
opposite to `uv export`'s default.

So each scope passes exactly the exclusion flags it needs (derived from
`pyproject.toml`'s own `[dependency-groups]` and
`[project.optional-dependencies]` tables), and each scope's `audited_packages`
is compared against an independent `uv export` count run with the matching
flags. A mismatch fails closed as **scope drift** rather than silently
auditing more than the label claims.

## Outcomes

`uv audit` exits `0` clean, `1` with findings, and `2` on any error. The
wrapper separates the error class:

| Outcome | Meaning | Exit |
| --- | --- | --- |
| Clean | No unsuppressed findings in any scope | `0` |
| Findings | An unsuppressed advisory matches a locked version, in any scope | `1` |
| Service outage | uv could not reach OSV (`Request failed after`, `error sending request for url`) | `0` under `--on-outage warn`, else `1`; never reported as clean |
| Tool error | Any other failure, including a stale or corrupt lock | `1`, always |
| Interface or scope drift | Unexpected JSON schema, a missing identity field, an exit code that disagrees with the report, or a scope-size mismatch | `1`, always |
| Invalid exceptions file | See below | `1`, always |

Only the two recognised connection-failure patterns count as an outage; every
other exit `2` -- including `Failed to parse \`uv.lock\`` -- is a tool error
and always fails, so a new, unrecognised failure mode fails rather than
passes. Identity fields (`id`, `aliases`, `fix_versions`, the dependency name
and version) are strict; descriptive fields (`summary`, `link`, `modified`)
may be null -- a real OSV entry does have a null `summary`
(`tests/fixtures/dependency_audit/vulnerable.json`).

Every finding prints its advisory ID and aliases, the package and locked
version, its scope, fix versions with the command to apply one
(`uv lock --upgrade-package <name>`), and the advisory link. When no fixed
version exists it says so and names the two choices: a reviewed exception, or
replacing the dependency.

## Enforcement

| Surface | Runs | Findings | Service outage |
| --- | --- | --- | --- |
| Pull request, push to `main` | `audit` job in `ci.yml`, part of `All checks passed` | fail | warn, loudly: the report says the audit did **not** run |
| Weekly schedule (Monday 06:00 UTC), manual dispatch | same job | fail | fail |
| Release (`release.yml`) | `audit` job that `release` needs | fail | fail; **no input bypasses it** -- rerun once the service is back |
| Locally | `uv run poe audit` (needs network) | fail | fail unless `-- --on-outage warn` |

A pull request warns on an outage because it is not that change's fault and
is not a clean result either, so it is reported rather than hidden. The
schedule exists precisely to make a persistent outage visible. A new advisory
against an unrelated dependency will fail pull requests until it is fixed or
excepted -- that is the gate working, and the response is the remediation
below.

The audit is not part of `linux-checks.yml`. It never installs the resolved
graph, only resolves and queries against the lock, so it does not depend on
the runner image -- the [runner canary](ci-runner-baseline.md) would only
repeat it for no reason.

## Exceptions

`.github/audit-exceptions.toml` is the only way to accept a finding, and it
ships empty. Each `[[exception]]` needs `id` (one advisory ID or alias),
`package`, `rationale`, `owner`, `added`, and `expires`. Anything else is
rejected, and the audit then fails closed:

- one literal package and one literal advisory, never a wildcard;
- unknown or missing keys, non-string text, a non-date date;
- `added` in the future, or `expires` before `added`;
- a lifetime over **90 days**. Re-review and renew instead of extending.

`expires` is the last day the exception applies. After it, the finding fails
again and the output names the lapsed exception. An entry that matches no
current finding is reported as stale (a warning, not a failure) and should be
removed. An exception is reviewed like code, in the pull request that adds
it; the `owner` is who re-reviews it before it expires. Prefer fixing the
dependency.

## Remediation

1. Read the finding: package, locked version, fix versions, advisory, scope.
2. Fix it: `uv lock --upgrade-package <name>`, then `uv run poe check`.
3. No fixed version: add a reviewed, expiring exception, or replace the
   dependency. Never suppress more broadly than one package and one advisory.
4. For a `[runtime]` or `[legacy]` finding, do the lower-bound review below.

## Lower-bound review

A lock-only upgrade fixes the audited graph. It does **not** by itself change
what the published wheel permits: `[project.dependencies]` (or
`[project.optional-dependencies].legacy`) keeps its declared floor, so a
consumer whose resolver picks the floor can still install a vulnerable
version.

For a `[runtime]`/`[legacy]` finding, ask whether the declared floor still
*permits* the vulnerable range. If it does and the vulnerability matters to
consumers, raising the floor follows the existing rule in [ADR
0038](adr/0038-dependency-floor-review.md) and
[CONTRIBUTING.md](../CONTRIBUTING.md#dependency-floors) -- a deliberate,
released decision, not a side effect of the lock refresh. If it does not
matter to consumers, record why in the pull request.

## Provider and client boundary

Each repository owns its own scanning. This audit covers `forge-template` as
one of `create-forge`'s locked dependencies; `forge-template` audits its own
lock independently ([FT-24.02](https://github.com/Sandsy09/forge-template/issues/192),
its ADR 0075). A finding in `forge-template`'s graph is reported and, if
necessary, excepted here, but the fix belongs to `forge-template`'s own
constraints or a patched release. Neither repository copies the other's
pipeline, and neither scans generated projects.

## Maintaining the pin

`UV_VERSION` appears in `ci.yml`, `linux-checks.yml`, and `release.yml`, and
is not updated by Dependabot ([docs/engine-updates.md](engine-updates.md)).
Because `uv audit` is preview, moving it is a deliberate change: run
`uv run poe audit`, confirm the scope cross-check still passes (22/29/73 on
this lock), and let the tests re-verify the JSON schema. A uv change that
moves the interface fails the audit visibly instead of passing quietly.

## Exclusions

No automatic dependency upgrades, no broad suppressions, no
generated-project scanning product, and no claim that a clean audit proves
security.

## Evidence

Recorded for CF-24.02 ([#199](https://github.com/Sandsy09/create-forge/issues/199)),
verified locally on 2026-09-27 with the real scanner on both uv `0.12.5` and
the pinned `0.12.0`:

| Case | Result |
| --- | --- |
| This repository | exit `0`; runtime 22, legacy 29, full 73, all clean |
| Probe project pinned to `jinja2==3.1.2` and `urllib3==1.26.4` | exit `1`; 28 findings, including a real null-`summary` entry |
| Unreachable service, `--on-outage warn` | exit `0`, reported as "NOT A CLEAN RESULT" |
| Unreachable service, `--on-outage fail` | exit `1` |
| Corrupted lock | exit `1`, a tool error even under `warn` |

The recorded fixtures under `tests/fixtures/dependency_audit/` are real
`uv audit` `0.12.5` output from this repository's lock and from the probe
project above.

CI run IDs (`audit` job, `All checks passed`, and the post-merge schedule,
dispatch, and release dry-run checks) follow in the completion evidence for
issue #199.
