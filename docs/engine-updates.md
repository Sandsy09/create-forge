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

The public engine is implemented by `forge-template`, beginning with its
documented `0.2.x` compatibility line, but it is not yet integrated here.
Today, `copier` is the compatibility-line dependency — the one
[CLAUDE.md](../CLAUDE.md) invariant 4 already singles out. After the engine
cutover, the `forge-template` engine package takes over that role.

## What the compatibility line is

| create-forge line | Compatibility-line dependency | Declared range | Status |
| --- | --- | --- | --- |
| v0.1.x | `copier` | `>=9.4,<10` | Current released architecture |
| First engine line | `forge-template` engine | *Unassigned* | Rules defined by ADR 0012; range assigned per [`docs/engine-resolution.md`](engine-resolution.md#assigning-the-first-engine-range) |

Only one dependency occupies this role at a time. `typer`, `questionary`,
`pydantic`, and `rich` are ordinary dependencies: unbounded above, freely
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

## Crossing a compatibility line

Automated tooling may propose updates *inside* the declared range only.
`.github/dependabot.yml`'s `uv` entry ignores `version-update:semver-major`
for `copier`; a pre-1.0 engine dependency's rule additionally ignores
`version-update:semver-minor`, since a minor version is itself a
compatibility line before 1.0. Crossing a line is a deliberate,
human-authored pull request that changes the declared bound, the code
depending on it (`runner.py` today; the engine adapter after cutover), and
the documented compatibility table in the same change.

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
| `uv` (`pyproject.toml` / `uv.lock`) | Dependabot | `ignore` rule blocks a major (and, for a pre-1.0 engine, minor) bump on the compatibility-line dependency |
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

## Where the supported range is recorded

[`docs/integration-contract.md`](integration-contract.md)'s compatibility
table is the single canonical record of the accepted range and protocol
version. A release's own notes narrate a change; they are not a second
source of truth the table can drift from.

## Executable examples

- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py) —
  `test_compatibility_line_dependency_keeps_a_strict_upper_bound` and
  `test_automation_cannot_cross_the_copier_compatibility_line` characterize
  today's `copier` gate; `test_declaring_the_engine_requires_a_matching_automation_gate`
  guards that declaring the `forge-template` dependency without a matching
  `.github/dependabot.yml` `ignore` rule fails the fast suite.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
