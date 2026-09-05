# Template-Engine Dependency Update Policy

This is the living contributor contract for how `create-forge` adopts updates
to its **compatibility-line dependency** — the one dependency whose version
range defines a supported integration line with `forge-template`.
[ADR 0010](adr/0010-public-engine-integration-contract.md) chose bounded
package ranges; [ADR 0011](adr/0011-engine-source-and-version-resolution.md)
defined how that dependency is resolved; [ADR 0012](adr/0012-engine-dependency-update-policy.md)
records the decision this document keeps current: how a compatible update is
adopted, how a breaking line is crossed, and what automated tooling may never
do on its own. Like [`docs/engine-resolution.md`](engine-resolution.md), the
*rules* below are the contract — today's mechanisms will change as the
engine cutover approaches.

## Status

`forge-template` is a real, released, installable dependency -- the optional
`engine` extra (#9, [ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md))
-- but reachable only via the hidden `new --engine-preview` flag, not the
default `new` path. Its range has crossed one compatibility line since it was
assigned:
[ADR 0026](adr/0026-adopt-the-0-4-engine-compatibility-line.md) moved it from
`>=0.3.1,<0.4` to `>=0.4,<0.5` following the procedure below. CF-14.01
([ADR 0031](adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md))
then adopted the reviewed `0.4.1` patch by raising the lower bound to
`>=0.4.1,<0.5`. `copier`
remains the compatibility-line dependency for the default path; the one
[CLAUDE.md](../CLAUDE.md) invariant 4 already singles out. **Two**
compatibility-line dependencies now exist simultaneously, each governing its
own path.

## What the compatibility line is

| create-forge line | Compatibility-line dependency | Declared range | Status |
| --- | --- | --- | --- |
| v0.1.x default `new` | `copier` | `>=9.4,<10` | Current released architecture |
| v0.2.x `engine` extra (`--engine-preview`) | `forge-template` | `>=0.3.1,<0.4` | Superseded by v0.3.x (ADR 0018) |
| v0.3.x `engine` extra (`--engine-preview`) | `forge-template` | `>=0.4.1,<0.5` | Current architecture (ADR 0031) |

Unlike the single-dependency framing this document previously used, both
rows are live at once: `copier` governs the default path, `forge-template`
governs the hidden engine-preview path, and each has its own Dependabot gate
below. Neither has replaced the other; the engine cutover that would retire
the `copier` row remains a future, unfiled decision. `typer`, `questionary`,
`pydantic`, and `rich` remain ordinary dependencies: unbounded above, freely
updated by Dependabot, out of scope for everything below.

## Adopting a compatible update

A release of the compatibility-line dependency inside its declared range is
an ordinary dependency bump, mergeable once the repository's required
`All checks passed` check is green. That check's `network` job is what makes
the bump trustworthy rather than merely passing: it runs
[`tests/test_drift.py`](../tests/test_drift.py) and
[`tests/test_update_network.py`](../tests/test_update_network.py) — a real
registry/`copier.yml` drift check and a real scaffold-then-update against
`forge-template`'s published tags. Once the engine exists, contract and
end-to-end tests exercising the exact supported package/protocol pair join
that job under the same rule: a compatibility-line PR is not mergeable on the
fast unit suite alone.

Adopting a compatible update never widens the declared bound. Widening the
bound is a line crossing, covered next.

CF-14.01 is the worked compatible-adoption example: provider review published
`0.4.1` without changing production source or protocols, so ADR 0031 raises
the lower bound from `>=0.4,<0.5` to `>=0.4.1,<0.5` while retaining the same
compatibility line and strict upper bound.

## Crossing a compatibility line

Automated tooling may propose updates *inside* the declared range only.
`.github/dependabot.yml`'s `uv` entry ignores `version-update:semver-major`
for `copier`, and, separately, both `version-update:semver-major` and
`version-update:semver-minor` for `forge-template` -- pre-1.0, a minor
version is itself a compatibility line, exactly the case ADR 0012 already
anticipated for whichever dependency occupied this role while still below
1.0. Crossing either line is a deliberate, human-authored pull request that
changes the declared bound, the code depending on it (`runner.py` for
`copier`; `src/create_forge/compat.py` for `forge-template`, and `engine.py`
only if the negotiation logic itself changes), and the documented
compatibility table in the same change.
[ADR 0026](adr/0026-adopt-the-0-4-engine-compatibility-line.md) is the
worked example: it moved `forge-template` from `>=0.3.1,<0.4` to
`>=0.4,<0.5` with no `engine.py` edit, because `0.4.0` preserved both
protocol tuples and every public signature.

Breaking changes then follow the sequence the
[integration contract](integration-contract.md#release-coordination) already
defines: release a new `forge-template` compatibility line, publish
compatibility and migration notes, prove ProjectSpec/discovery/rendering/
update paths against the exact pair, then release the adopting `create-forge`
line with matching bounds. This document does not restate that sequence in
full — it supplies the rule that keeps automation from bypassing its first
step.

## What automation may and may not do

| Surface | Automated by | Compatibility-line gate |
| --- | --- | --- |
| `github-actions` | Dependabot | None needed — not a compatibility-line dependency |
| `uv` (`pyproject.toml` / `uv.lock`) | Dependabot | separate `ignore` rules block a major bump on `copier` and a major-or-minor bump on `forge-template` (pre-1.0) |
| `.pre-commit-config.yaml` pinned hook revisions | Nobody | Known gap, tracked separately — [issue #17](https://github.com/Sandsy09/create-forge/issues/17); out of scope here |

The `.pre-commit-config.yaml` gap is the same one that produced the stale
ruff pin `.github/dependabot.yml`'s own comment describes. It is a real,
already-filed gap in a different surface — dev tooling, not the
compatibility line — and this decision does not close it.

## Existing generated projects

A compatibility-line adoption, inside a line or crossing one, requires a
supported `create-forge update` path or an explicit, tested migration for
projects generated under the prior line.
[`tests/test_update_network.py`](../tests/test_update_network.py) is the
standing evidence for that path today: it scaffolds at `forge-template`'s
first tag and updates to its second, against the real registry. Dropping the
update path without a tested migration is not an acceptable adoption,
whether proposed by a human or by automation.

This rule binds the default `new` path, whose generated projects track a
`forge-template` Copier tag. The `--engine-preview` path has no equivalent
obligation yet: it is a hidden, dev-only flag that has never been the
default and writes no engine answers file, so there are no released
engine-generated projects to migrate. ADR 0026's move to the 0.4 line was
therefore vacuously compliant here; a future engine-first cutover is what
gives the engine path its own update contract.

## Where the supported range is recorded

[`docs/integration-contract.md`](integration-contract.md)'s compatibility
table is the single canonical record of the accepted range and protocol
version. A release's own notes narrate a change; they are not a second
source of truth the table can drift from.

## Executable examples

- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py) —
  `test_compatibility_line_dependency_keeps_a_strict_upper_bound` and
  `test_automation_cannot_cross_the_copier_compatibility_line` characterize
  the `copier` gate; `test_forge_template_compatibility_line_keeps_a_strict_upper_bound`
  and `test_automation_cannot_cross_the_forge_template_compatibility_line`
  characterize the `forge-template` gate the same way, now that #9
  ([ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)) has
  declared it.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
