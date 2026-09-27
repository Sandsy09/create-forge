# 59. Audit resolved dependencies with `uv audit`

## Status

Accepted

## Context

[Issue #199 / CF-24.02](https://github.com/Sandsy09/create-forge/issues/199),
a child of [CF-EPIC-24](https://github.com/Sandsy09/create-forge/issues/190),
reports that Dependabot and Action pinning ([ADR
0037](0037-immutable-workflow-actions.md)) keep dependencies current and
Actions immutable, but neither checks a *resolved* version against a
vulnerability database. Only a manual `gh api graphql` probe existed, and only
for the `copier` floor before a release ([ADR
0038](0038-dependency-floor-review.md)).

`forge-template` did the equivalent work first
([FT-24.02](https://github.com/Sandsy09/forge-template/issues/192), its ADR
0075) and chose `uv audit`. This repository is not the same shape --- it has
an optional extra (`legacy`) the provider does not --- so the scope logic here
is written for this repository's dependency-groups/extras rather than copied,
per the acceptance criteria's "no copied provider audit pipeline" rule.
Verified independently, against this repository's own lock, on both `uv
0.12.0` (the CI pin) and `0.12.5`:

- `uv audit --output-format json` returns a `{schema, summary, vulnerabilities,
  adverse_statuses}` report; exit `0` clean, `1` with findings, `2` on error.
- **`uv audit` includes every optional extra by default** (73 packages on this
  lock with no flags at all, versus 68 with `--no-extra legacy`).
  `--no-default-groups` and `--only-dev` do **not** narrow the audit -- both
  still cover the whole 68/73-package graph. Only `--no-group <name>` and
  `--no-extra <name>` narrow it.
- An unreachable service exits `2` with `Request failed after N retries` /
  `error sending request for url (...)` on stderr; a corrupt or stale
  `uv.lock` also exits `2`, with `Failed to parse \`uv.lock\`` -- a different
  message that must not be mistaken for an outage.
- A real OSV entry can have a null `summary` (`PYSEC-2021-108` against
  `urllib3`, recorded in `tests/fixtures/dependency_audit/vulnerable.json`).

## Decision

1. **Use `uv audit`, pinned and fail-closed**, in `scripts/audit_dependencies.py`.
   `pip-audit` was rejected: it cannot read `uv.lock`, so CI would need a
   second, driftable `uv export` artefact and a new dev dependency, for no
   benefit over reading the lock directly.
2. **Three scopes, derived from `pyproject.toml`, not hardcoded:** `runtime`
   (`[project.dependencies]` and its lock -- what the wheel depends on), one
   scope per optional extra (today, `legacy`: runtime plus that extra), and
   `full` (every extra and every dependency group). A new group or extra
   therefore narrows the right scope automatically, without a code change.
3. **Derive and cross-check the scope**, because `--no-default-groups` and
   `--only-dev` are silently ineffective. Each scope's `audited_packages` is
   compared against an independent `uv export` count with the matching
   `--no-default-groups`/`--extra`/`--all-*` flags; a mismatch fails closed as
   scope drift rather than silently auditing more than the label claims.
4. **Separate the outcomes**: clean, findings, service outage (only the two
   recognised connection-failure patterns above; every other exit `2` --
   including a stale lock -- is a tool error and always fails), and interface
   drift (unexpected schema version, a missing identity field, an exit code
   that disagrees with the report, or scope drift). Only identity fields
   (`id`, `aliases`, `fix_versions`, the dependency name and version) are
   required and strict; descriptive fields (`summary`, `link`, `modified`) may
   be null.
5. **Findings are attributed to the narrowest scope that contains them.**
   `runtime` is scanned first, then each extra, then `full`; a finding already
   reported in a narrower scope is not repeated in a broader one. A finding
   that only ever appears in `full` is development-only (lint/test/docs/
   typecheck) and is labelled `[full]`.
6. **Every unsuppressed finding fails, including a development-only one**
   (the user's explicit choice: a vulnerable CI tool is still a vulnerable
   tool sitting in the lock). Only `runtime`/extra-scope findings prompt the
   lower-bound review below; a `[full]` finding never reaches a consumer, so
   it does not.
7. **Enforcement differs only on an outage, and only on pull requests and
   pushes to `main`.** There the audit warns loudly on an outage --- it is not
   that change's fault, and the annotation says the audit did not run, never
   reporting it as clean --- but still fails on any finding. The weekly
   schedule, manual dispatch, and `release.yml`'s own `audit` job (which
   `release` `needs`, no bypass input) fail on both. This is the user's
   explicit choice for the PR surface; every other surface fails closed.
8. **Exceptions are reviewed, scoped and expiring.**
   `.github/audit-exceptions.toml` ships empty; each entry names exactly one
   advisory ID (or alias) and one package, an owner, a rationale, `added`, and
   `expires` at most 90 days later. A lapsed exception stops suppressing and
   is reported by name; an entry matching no current finding is reported as
   stale (a warning, not a failure). uv's own `--ignore` was rejected: it has
   no owner, rationale, or expiry.
9. **The audit lives in `scripts/`, not the wheel** -- like `check_wheel.py`
   and `check_workflows.py`, it never ships to a user.
10. **Each repository scans its own installed graph.** This repository's
    audit covers `forge-template` as a locked dependency; a finding there is
    reported and, if necessary, excepted here, but the fix belongs to
    `forge-template`'s own constraints or a patched release. No pipeline is
    copied in either direction, and generated projects are not scanned by
    either repository.
11. **A lock-only upgrade is not a floor change.** `uv lock --upgrade-package`
    fixes the audited graph; it does not by itself raise
    `[project.dependencies]`'s declared floor, so a consumer resolving to that
    floor can still install a vulnerable version. Raising a floor stays a
    deliberate, released decision under [ADR
    0038](0038-dependency-floor-review.md)'s existing rule, not a side effect
    of a lock refresh.

## Consequences

- A vulnerable locked package -- runtime, `legacy`, or development-only --
  now fails the pull request that introduces it and the weekly run that
  discovers it, joining `All checks passed` via the new `audit` job in
  `ci.yml`.
- A release always fails on a finding or an outage, with no bypass; a
  persistent OSV outage blocks releases until the service returns, by design.
- The audit depends on `uv audit`, a preview command whose JSON schema is
  itself `"preview"`. `scripts/audit_dependencies.py` accepts exactly that
  schema value and fails as drift on anything else, so a uv upgrade that
  changes the interface fails visibly instead of silently auditing less (or
  nothing).
- OSV has no snapshot version, so a run cannot be reproduced later; the
  evidence is the recorded `uv --version`, the UTC query time, and each
  finding's own advisory `modified` timestamp.
- The audit does not depend on the runner image, so it lives in `ci.yml`
  directly rather than in the reusable `linux-checks.yml` --- the
  `ubuntu-26.04` canary ([ADR 0058](0058-pin-the-ubuntu-runner-baseline-with-a-canary.md))
  would otherwise repeat it for no reason.
- No published artefact, CLI surface, or compatibility contract changes; only
  repository CI and tooling.
