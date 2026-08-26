# 12. Adopt engine updates within one compatibility line behind a review gate

## Status

Accepted

## Context

[ADR 0010](0010-public-engine-integration-contract.md) chose one versioned
`forge-template` engine-and-assets release unit with bounded package ranges
and a separately versioned ProjectSpec protocol. [ADR 0011](0011-engine-source-and-version-resolution.md)
then defined how that unit is *resolved* — as an ordinary, install-time
bounded dependency, with no runtime fetch — and explicitly deferred two
remaining questions to CF-05.02
([issue #45](https://github.com/Sandsy09/create-forge/issues/45)): the update
*cadence* once a bound exists, and the distribution *channel* the dependency
resolves from.

The cadence question is not hypothetical. `copier>=9.4,<10` is already the
compatibility-line dependency in this repository — [CLAUDE.md](../../CLAUDE.md)
invariant 4 treats a Copier major bump as a deliberate event requiring
attention in `runner.py`, since it is the one module that touches Copier's
Python API. But nothing enforces that today. `.github/dependabot.yml`'s `uv`
ecosystem entry has no `ignore` rule, so Dependabot is free to open a PR
widening that bound to `copier>=10`, and `main`'s branch protection requires
only the `all-green` aggregate check with zero approving reviews. The
invariant exists only as prose a reviewer must remember.

The `forge-template` engine package does not exist yet
(`FT-06.07` is still open, and `forge-template`'s own `pyproject.toml`
classifies it `Private :: Do Not Upload`), so this decision cannot assign a
concrete engine range or choose a distribution channel — a channel is
downstream of `forge-template` publishing at all, which is that repository's
call, not this one's.

## Decision

**Adoption inside a declared line.** A release of the compatibility-line
dependency within its declared range — pre-1.0 `>=0.y.a,<0.(y+1)`, from 1.0
`>=n.a,<n+1`, per the [integration contract](../integration-contract.md) — is
adopted as an ordinary dependency bump once the repository's required
`all-green` check passes. Adoption never widens the declared bound; widening
the bound is itself a line crossing, handled below.

**Proof before adoption.** No compatibility-line bump merges without the
`network` CI job passing. Today that job runs `tests/test_drift.py` and
`tests/test_update_network.py` — a real registry/`copier.yml` drift check and
a real scaffold-then-update against `forge-template`'s published tags. Once
the engine exists, contract and end-to-end tests exercising the exact
supported package/protocol pair join that same job, and the same rule binds
them: a compatibility-line PR is not mergeable on unit tests alone.

**Crossing a line is never automatic.** Automated dependency tooling may
propose updates *inside* the declared range only. `.github/dependabot.yml`'s
`uv` entry carries an `ignore` rule blocking `version-update:semver-major` for
`copier` — the current compatibility-line dependency — so a new Copier major
never arrives as an unreviewed-by-design PR. When a pre-1.0 engine dependency
is later declared, its `ignore` rule additionally blocks
`version-update:semver-minor`, since a minor version *is* a compatibility
line before 1.0. Crossing a line is a deliberate, human-authored pull request
that changes the declared bound, the code depending on it (`runner.py` today;
the engine adapter after cutover), and the documented compatibility table in
the same change.

**Breaking lines follow the integration contract's existing sequence.** The
[integration contract](../integration-contract.md)'s "Release coordination"
section already defines the order: release a new `forge-template`
compatibility line, publish compatibility and migration notes, prove
ProjectSpec/discovery/rendering/update paths against the exact pair, then
release the adopting `create-forge` line with matching bounds. This decision
does not restate that sequence; it supplies the rule that keeps automation
from bypassing the first step of it. The canonical record of an accepted
range is that document's compatibility table — a release's own notes narrate
the change but are not a second source of truth for the range itself.

**Existing generated projects.** A compatibility-line adoption — inside a
line or crossing one — requires a supported `create-forge update` path or an
explicit, tested migration for projects generated under the prior line.
Dropping the update path without a tested migration is not an acceptable
adoption, whether proposed by a human or automation.

**Scope.** This policy governs the compatibility-line dependency only:
`copier` today, the `forge-template` engine after cutover. It does not extend
to `typer`, `questionary`, `pydantic`, `rich`, or dependency-group tooling —
those remain ordinary, unbounded, and fully automatable, as they are today.
Nor does it extend to `.pre-commit-config.yaml`'s pinned hook revisions,
which Dependabot does not cover at all
([issue #17](https://github.com/Sandsy09/create-forge/issues/17)); that is a
separate, already-tracked gap, referenced but not resolved here.

**Channel remains deferred.** Which index or mechanism the compatibility-line
dependency resolves from is unchanged by this decision and stays with
[PyPI publishing / issue #9](https://github.com/Sandsy09/create-forge/issues/9).
The rules above hold identically whether the dependency resolves from a
package index or a pinned VCS revision, and a channel cannot be chosen while
`forge-template` remains `Private :: Do Not Upload` — that classification is
`forge-template`'s own decision to change.

## Consequences

- A new Copier major, or later a new engine major (or pre-1.0 minor), no
  longer arrives as an open PR; discovering that a new line exists becomes a
  deliberate act. The existing Monday `network` cron and this decision's
  guard tests reduce that cost but do not remove it — nothing pushes a
  notification when an ignored update exists upstream.
- `.github/dependabot.yml` becomes a contract-bearing file: a test now reads
  it, so editing the `ignore` block without updating the corresponding guard
  is caught by the fast suite rather than discovered at review time.
- The gate is executable rather than procedural. It fires the moment a
  `forge-template` dependency is declared without a matching `ignore` rule,
  the same day `tests/test_engine_contract.py`'s "no engine dependency
  declared" branches stop being true.
- CF-05.02 closes without assigning a channel; `#9` remains its sole owner,
  now carrying a narrower, already-scoped question.
- Nothing about v0.1.x behaviour changes. `copier>=9.4,<10` is unchanged; only
  the automation permitted to touch that bound is now restricted.
