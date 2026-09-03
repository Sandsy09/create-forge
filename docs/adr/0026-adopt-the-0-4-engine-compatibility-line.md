# 26. Adopt the forge-template 0.4 compatibility line

## Status

Accepted

## Context

[Issue #106 / CF-13.01](https://github.com/Sandsy09/create-forge/issues/106)
is the first child of
[CF-EPIC-13](https://github.com/Sandsy09/create-forge/issues/103), which
exposes the Data Science archetype and its reusable capabilities through
`new --engine-preview`. Every later child in that epic needs the engine that
ships those components; this one does nothing else.

[ADR 0018](0018-pypi-distribution-and-the-first-engine-range.md) assigned the
first released engine range, `forge-template>=0.3.1,<0.4`, as the optional
`engine` extra. `forge-template` has since published
[`0.4.0`](https://github.com/Sandsy09/forge-template/releases/tag/v0.4.0) to
[PyPI](https://pypi.org/project/forge-template/0.4.0/) — the five-component
line (`library`, `cli`, `data-science`, `jupyter`, `scientific-python`) whose
provider hand-off (FT-12.04) is complete and immutable. Under
[ADR 0012](0012-engine-dependency-update-policy.md), a pre-1.0 minor bump is
itself a new compatibility line: Dependabot is barred from proposing it, and
adopting it is a deliberate, human-authored change that moves the declared
bound, the depending code, and every compatibility table together. Until that
change, normal resolution must keep rejecting `0.4.0`.

The move is low-risk. `git diff v0.3.2..v0.4.0` over the public facade
(`__init__.py`, `engine.py`, `project_spec.py`, `component_manifest.py`) is
empty. Every protocol integer is unchanged — ProjectSpec `1`, component
manifest `(1, 2)`. `requires-python` stays `>=3.11`; the runtime dependency
set (`jinja2`, `packaging`, `pydantic`) is untouched. The only
client-observable deltas are additive: `discover_components()` returns five
descriptors instead of two, and generated `library`/`cli` `pyproject.toml`
bytes shift slightly from three new, empty-when-unselected Foundation
extension points.

## Decision

1. **Move the declared range to `forge-template>=0.4,<0.5`.**
   `src/create_forge/compat.py`'s `SUPPORTED_ENGINE_RANGE` and
   `pyproject.toml`'s `[project.optional-dependencies].engine` change
   together, and `uv.lock` is regenerated
   (`uv lock --upgrade-package forge-template`) so the committed lock
   resolves `0.4.0`. `engine.py`, `cli.py`, and `spec.py` need no edit — every
   range and protocol string they emit is interpolated from `compat`.

2. **Leave both protocol tuples unchanged.**
   `SUPPORTED_PROJECTSPEC_PROTOCOLS` stays `(1,)` and
   `SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS` stays `(1, 2)`. The zero-diff
   public facade between `0.3.2` and `0.4.0` is the evidence: this is a range
   move, not a protocol migration.

3. **Record the released line as superseded, not rewritten.** The published
   `create-forge` `0.2.1` wheel genuinely declares `>=0.3.1,<0.4`, so
   `docs/integration-contract.md`'s compatibility table (the single canonical
   record, per [ADR 0012](0012-engine-dependency-update-policy.md) and
   `docs/engine-updates.md`) marks the `v0.2.x` row *Superseded by v0.3.x*
   and adds a `v0.3.x (engine extra) | forge-template>=0.4,<0.5 | 1
   (supported)` row for what `main` now supports. `pyproject.toml`'s version
   stays `0.2.1`; the bump belongs to a later release pull request
   ([ADR 0009](0009-pyproject-as-the-single-version-source.md)).

4. **Keep the Dependabot gate as it is.** `.github/dependabot.yml` already
   ignores both `semver-major` and `semver-minor` for `forge-template`, and
   `tests/test_engine_contract.py`'s pre-1.0 detection (`re.search(r">=0\.",
   spec)`) still matches `>=0.4`, so the gate stays armed against the next
   line.

5. **Add no component identifier or catalogue rule to this repository.** The
   new-line proof in `tests/test_engine_cross_repository.py` asserts the
   catalogue arrived by descriptor *kind* and relationship *shape* — at least
   one `capability`, at least one descriptor declaring a `requires` relation —
   never by naming `data-science`, `jupyter`, or `scientific-python`.
   Discovering and selecting those components is CF-13.02–13.04; proving the
   Data Science pipeline is CF-13.05.

## Consequences

- `create-forge doctor` and `doctor --json` report
  `forge-template>=0.4,<0.5`; `--engine-preview` against an installed
  `0.3.x` or an out-of-range engine still fails closed with exit status `3`
  before any destination write.
- `tests/test_engine_contract.py`'s `ENGINE_REQUIREMENT` constant and its
  asserted `docs/integration-contract.md` table row move to the `v0.3.x` row;
  `tests/test_engine_adapter.py` and `tests/test_engine_cross_repository.py`
  gain `0.3.2` (the previous line's latest release) as the below-lower-bound
  rejection case and `0.5.0` as the excluded-upper-bound case, and derive the
  range string from `compat.SUPPORTED_ENGINE_RANGE` rather than re-hardcoding
  it. `tests/test_e2e_engine_generation.py` is unchanged — its `v0.3.0`
  git-tag out-of-range fixture stays valid, as
  [ADR 0020](0020-engine-path-end-to-end-tests.md) pre-authorised.
- `examples/downstream_cli.py`'s own independently-declared
  `SUPPORTED_ENGINE_RANGE` moves to `>=0.4,<0.5` too: its `main()` negotiates
  against the real installed engine, so leaving it stale would make the
  shipped reference client reject the engine this repository now locks. The
  comment's point — that it declares its bounds independently and merely
  happens to match — is preserved.
- The living contracts that carry the range or a "until CF-13.01" forward
  reference are rewritten in this same change:
  `docs/integration-contract.md`, `docs/engine-resolution.md`,
  `docs/engine-updates.md`, `docs/engine-contract-tests.md`,
  `docs/component-discovery.md`, `docs/project-spec-construction.md`,
  `docs/end-to-end-tests.md`, `docs/cross-repository-workflow.md`, plus
  `README.md`, `CLAUDE.md`, and `CONTRIBUTING.md`. `docs/end-to-end-tests.md`
  also loses an already-stale rationale ("since `0.3.1` is currently the only
  PyPI release").
- `docs/engine-updates.md`'s "Existing generated projects" rule — which
  requires a supported `create-forge update` path or a tested migration for
  projects generated under the prior line — is satisfied vacuously. The
  engine path is a hidden, dev-only preview flag that has never been the
  default and writes no answers file; there are no released engine-generated
  projects to migrate.
- `forge-template`'s own `docs/compatibility-policy.md` still states
  "Released create-forge declares the compatible `forge-template>=0.3.1,<0.4`
  engine range." That is now stale provider-side documentation, left for
  [FT-EPIC-14](https://github.com/Sandsy09/forge-template/issues/99)'s
  provider review; `0.4.0` is already released and immutable, so no
  coordinated merge order applies.
- This is **not** the CLI cutover. The default `new` command remains the
  v0.1.x direct-Copier path with a bundled registry; `--engine-preview` stays
  hidden; and no capability selection, prompt, flag, engine model, or policy
  resolver is added here.
