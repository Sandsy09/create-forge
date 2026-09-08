# 38. Raise the Copier floor past the destination-escape advisories and hold uv

## Status

Accepted

## Context

`create-forge` advertised `copier>=9.4,<10` and, on the `engine` extra,
`uv>=0.12,<0.13`. Both floors were set once and never reviewed. Dependabot
PRs #136 and #137 moved the lock — uv `0.12.7` → `0.12.10`, Copier `9.17.2` →
`9.18.2` — without touching either published bound, so the development
environment had drifted well above what a fresh `pip install create-forge`
resolves. Nothing in the repository tested the floors either: every CI job
resolves the newest satisfying release, so `>=9.4` was an assertion.

The GitHub Advisory Database settles the Copier half. `copier>=9.4` admits
five advisories in which a *safe* template reads or writes outside the
destination — which contradicts the target-safety guarantee in
[`docs/filesystem-generation.md`](../filesystem-generation.md), and bites
regardless of trust:

| Advisory | Severity | Fixed in |
| --- | --- | --- |
| `GHSA-3xw7-v6cj-5q8h` — arbitrary filesystem read/write | HIGH | 9.9.1 |
| `GHSA-p7q8-grrj-3m8w` — write outside the destination path | MODERATE | 9.9.1 |
| `GHSA-xjhm-gp88-8pfx` / `GHSA-4fqp-r85r-hxqh` — symlink read/write escape | MODERATE | 9.11.2 |
| `GHSA-85v3-4m8g-hrh6` — `_subdirectory` template-root escape | MODERATE | 9.14.1 |
| `GHSA-hgjq-p8cr-gg4h` — `_external_data` traversal / absolute local read | MODERATE | 9.14.1 |

`9.14.1` is the strict minimum that clears this set. A sixth advisory,
`GHSA-9gmc-jqmh-3rvm` (HIGH, fixed `9.15.2`), and further trust hardening in
`9.18.0` and `9.18.2`, concern Copier's *trust prefix* — the gate that decides
whether a template's `_tasks` run unprompted. That gate does not protect a
`create-forge` user: `runner.py` passes `unsafe=True` unconditionally
([ADR 0005](0005-execute-template-tasks.md), CLAUDE.md invariant 3), so what
bounds task execution here is the bundled, reviewed URL registry and the
`--template-url` confirmation prompt, never Copier's trust check. Those
advisories therefore do not raise the *required* floor — but pinning one patch
past them, at `9.15.2`, buys a simpler and re-verifiable rule: no supported
Copier version carries any published advisory.

The `9.15.2` floor deliberately predates the Copier `9.18.x` line that PR #137
tracked. Two things land in `9.18.0`–`9.18.2` that a review has to weigh and
set aside:

- **Windows path / SCP-URL disambiguation in the trust check** (`9.18.1`,
  `9.18.2`). This hardens the same trust prefix the `GHSA-9gmc-jqmh-3rvm`
  fix did, and is moot here for the same reason — `unsafe=True` means the
  trust gate never decides anything for a `create-forge` user.
- **Preserving the original error when cleanup fails** (`9.18.0`, copier
  #2824). A developer-experience improvement to Copier's own failure path.
  `runner.py` owns its error boundary (`_explain`, ADR 0036) and
  `staging.py` owns cleanup on the engine path, so this does not change what
  a `create-forge` user sees on a failed generation.

Neither is a floor-raising reason. The CI `floor` job runs the real scaffold
and `create-forge update` paths at `9.15.2`, and the `windows` job runs the
fast suite on `windows-latest`, so default generation, update, and Windows
path handling are all exercised at the pinned lower bound.

uv is the mirror image. All five published uv advisories are fixed at
≤ `0.11.15`, so the entire declared `>=0.12,<0.13` range is already
advisory-free. `create-forge` invokes exactly one uv command —
`uv lock --directory` from `staging.create_uv_lock`
([ADR 0021](0021-client-finalises-engine-lockfiles.md)) — present throughout
`0.12.x`. The fast suite's `staging` tests run at the floor in the new CI
job; the `engine`-path end-to-end suites exercise real engine lock creation
and `uv lock --check` at the resolved (newest) uv, and the Python matrix runs
`3.11`–`3.14`. Yet [`docs/engine-updates.md`](../engine-updates.md) never
classified uv at all, neither compatibility-line nor ordinary, so holding the
bound had to be recorded as a decision rather than left as an omission.

[ADR 0004](0004-copier-python-api-over-subprocess.md) and
[ADR 0012](0012-engine-dependency-update-policy.md) both quote the old
`copier>=9.4,<10` figure. They are immutable and unchanged; this record
supersedes neither decision — ADR 0004 confines Copier's API to `runner.py`,
ADR 0012 governs how updates are adopted — it revises a number they cite.

## Decision

1. **Raise the Copier floor to `copier>=9.15.2,<10`.** The strict minimum for
   the destination-escape advisories is `9.14.1`; `9.15.2` is one patch
   further and clears every published Copier advisory, so the supported range
   carries no known advisory of any kind. The upper bound is unchanged — this
   is not a compatibility-line crossing.

2. **Hold the uv floor at `uv>=0.12,<0.13`, reviewed and unchanged.** Every
   published uv advisory is fixed below `0.12`, and `create-forge` uses only
   `uv lock`, stable across `0.12.x`. There is no advisory or behavioural
   reason to move it; the lock tracking `0.12.10` is not one.

3. **Classify uv in the update policy as a bounded ordinary dependency.** It
   is not a compatibility-line dependency — no integration contract turns on
   its version — but it keeps a real upper bound, because a pre-1.0 minor is
   itself a line, so a `0.13` proposal is a human decision, not an automatic
   merge. [`docs/engine-updates.md`](../engine-updates.md) records this.

4. **Test the advertised floors in CI.** A new `floor` job runs the fast
   suite under `uv --resolution lowest-direct`, pinning every direct
   dependency to the bottom of its declared range, so `copier>=9.15.2` and the
   `engine` extra's floors are exercised rather than asserted. It is wired
   into the `all-green` aggregate check. The job immediately found that
   `typer>=0.15` was not a working floor — `typer 0.15.0`–`0.15.3` break
   against `click >=8.2` — so the bound moves to `typer>=0.16`, the first
   release compatible with current `click`.

5. **Move a dependency floor only on advisory or required-behaviour
   evidence.** A lockfile bump is not evidence. The floor claim is only as
   good as the day the advisory database was last checked, so re-verify it
   (`gh api graphql … securityVulnerabilities`) before changing a bound.
   `tests/test_engine_contract.py` pins the Copier floor by exact string, the
   same way it already pins the `forge-template` and uv requirements.

## Consequences

- A fresh `pip install create-forge` can no longer resolve a Copier version
  with a known destination-escape advisory. Anyone currently on `9.4`–`9.15.1`
  is asked to upgrade on their next `create-forge` update.
- `create-forge` moves to `0.3.1`, a patch release whose user-visible changes
  are the raised `copier` and `typer` floors. Wheel metadata, the changelog,
  and the installed console-script path are verified in that release.
- The `typer>=0.16` floor is a real narrowing of the supported install range,
  but from a floor that did not work: at `typer 0.15.x` + `click >=8.2`, a
  malformed `--data` or `--component-option` crashed with a `TypeError`
  instead of the exit-2 usage error `docs/cli-conventions.md` promises.
- The `floor` CI job re-resolves `uv.lock` inside the runner by design; it
  must never be paired with a `--locked` check. Its Python is `3.11`, the
  `requires-python` floor.
- uv gains no Dependabot `ignore` rule. `<0.13` already fails the build if a
  `0.13` release is proposed, and an `ignore` rule would instead hide that a
  new line exists — the opposite of what the `forge-template` and `copier`
  rules achieve, where the human PR is the *only* path across.
- This changes the advertised install range and the CI matrix only. It does
  not cross the Copier compatibility line, change the engine range or
  protocol, perform the engine cutover, or require a `forge-template` release.
