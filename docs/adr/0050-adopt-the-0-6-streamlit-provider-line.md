# 50. Adopt the forge-template 0.6 Streamlit provider line

## Status

Accepted

## Context

[Issue #165 / CF-21.01](https://github.com/Sandsy09/create-forge/issues/165)
is the first child of
[CF-EPIC-21](https://github.com/Sandsy09/create-forge/issues/154), which
adopts the Streamlit archetype in the client. Its blocker,
[FT-20.04](https://github.com/Sandsy09/forge-template/issues/162), closed on
2026-09-20 with the publication of
[`forge-template 0.6.0`](https://github.com/Sandsy09/forge-template/releases/tag/v0.6.0)
to [PyPI](https://pypi.org/project/forge-template/0.6.0/) — an immutable
provider release, not a moving branch, as the roadmap requires.

[ADR 0042](0042-engine-cutover-acceptance-and-support-policy.md) assigned the
`forge-template>=0.5,<0.6` range that published `create-forge 0.4.0` declares.
Under [ADR 0012](0012-engine-dependency-update-policy.md), a pre-1.0 minor
bump is itself a new compatibility line: Dependabot is barred from proposing
it, and adopting it is a deliberate, human-authored change that moves the
declared bound, the depending code, and every compatibility table together.
Until that change, normal resolution must keep rejecting `0.6.0`.

The move is low-risk, and the evidence is measured rather than taken from the
provider's own prose. Over `v0.5.0..v0.6.0` in `forge-template`:

- `git diff` over the public facade (`__init__.py`, `engine.py`,
  `project_spec.py`, `component_manifest.py`) is empty;
- the only source change is the new `streamlit` component and a one-line
  docstring edit in `render.py`;
- `pyproject.toml` changes its version and task metadata but no dependency and
  not `requires-python`; and
- the Copier `template/` and `copier.yml` are untouched, so the `--legacy`
  path cannot move.

The installed `0.6.0` reports ProjectSpec protocol `(1,)`, component-manifest
protocols `(1, 2, 3)` and `metadata_version` `1` — all unchanged — and
`discover_components()` returns fifteen descriptors instead of fourteen. The
one addition is `streamlit`: an archetype at component version `1.0.0` that
declares no `requires`, `conflicts` or options, so it is catalogue data behind
an unchanged facade. The provider's
[compatibility and acceptance contract](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-compatibility-and-acceptance.md)
classifies exactly two versioned axes as moving — the package and the
discovered components — and names this adoption as the client's gate.

## Decision

1. **Move the declared range to `forge-template>=0.6,<0.7`.**
   `src/create_forge/compat.py`'s `SUPPORTED_ENGINE_RANGE` and
   `pyproject.toml`'s `[project.dependencies]` entry change together, and
   `uv.lock` is regenerated so the committed lock resolves `0.6.0`. The lock
   diff is the `forge-template` package alone. `engine.py`, `cli.py` and
   `spec.py` need no edit — every range and protocol string they emit is
   interpolated from `compat`.

2. **Leave every protocol tuple unchanged.**
   `SUPPORTED_PROJECTSPEC_PROTOCOLS` stays `(1,)`,
   `SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS` stays `(1, 2, 3)` and
   `SUPPORTED_GENERATION_METADATA_VERSIONS` stays `(1,)`. The zero-diff public
   facade is the evidence: this is a range move, not a protocol migration.

3. **Select Streamlit only through the generic contract.** No production module
   names `streamlit` to decide catalogue, validation, composition or generated
   content behaviour (CF-ROADMAP-02-AC-03). The proof is executable:
   `tests/test_archetype_parity.py`'s parametrisation over every discovered
   archetype now covers a fourth archetype without an edit; a named tripwire
   asserts `streamlit` is discovered as an optionless archetype; and a guard
   walks *every* module under `src/create_forge` for a `streamlit` string
   literal — wider than the existing five-module component-id guard, because
   the acceptance criterion says "no production module". The new
   `tests/test_streamlit_adoption.py` drives a real non-interactive
   (`--archetype streamlit --yes`) and a real interactive `new` through
   staging and finalisation.

4. **Do not expose Streamlit through the Copier registry.** `templates.toml`
   stays Library-only. The default engine path reaches Streamlit; `--legacy`
   never does (CF-ROADMAP-02-EX-01).

5. **Record the line on the `v0.4.x` row, not a new one.** The published
   `create-forge 0.4.0` wheel genuinely declares `>=0.5,<0.6`, but
   `pyproject.toml`'s version stays `0.4.0` — the release version belongs to
   CF-21.03 ([ADR 0009](0009-pyproject-as-the-single-version-source.md)) — and
   `INTEGRATION_LINE` is deliberately tied to that version's major and minor.
   So `docs/integration-contract.md`'s compatibility table (the single
   canonical record, per [ADR 0012](0012-engine-dependency-update-policy.md))
   moves the `v0.4.x` row to the new range and records in its Status cell that
   the range is unreleased and the published `0.4.0` declares the previous
   one. This differs from [ADR 0026](0026-adopt-the-0-4-engine-compatibility-line.md),
   which added a row only because a new client line accompanied its crossing.

6. **Keep the Dependabot gate as it is.** `.github/dependabot.yml` already
   ignores both `semver-major` and `semver-minor` for `forge-template` by
   dependency name, and `tests/test_engine_contract.py`'s pre-1.0 detection
   still matches `>=0.6`, so the gate stays armed against the `0.7` line.

7. **Prove the previous line is rejected.** The out-of-range fixtures in
   `tests/test_engine_adapter.py`, `tests/test_engine_cross_repository.py` and
   `tests/test_data_science_pipeline.py` gain `0.5.0` — the previous line's
   release, which a client must no longer silently accept — and move the
   excluded-upper-bound case to `0.7.0`, because `0.6.0` is now in range.
   Together they assert the rejection, that no public engine call runs before
   it, and that a rejected `new` writes nothing.

This decision does not choose the next `create-forge` version, release
anything, or validate installed Streamlit generation. Those are CF-21.03 and
CF-21.02 respectively.

## Consequences

- `create-forge doctor` and `doctor --json` report `forge-template>=0.6,<0.7`.
  An installed engine outside it — including the previous `0.5.x` line — still
  fails closed with exit status `3` before any destination write.
- `tests/test_engine_contract.py`'s `ENGINE_REQUIREMENT` constant, the
  installed-candidate e2e pin `tests/installed_client.py`'s `ENGINE_VERSION`,
  and the fixtures modelling the currently supported engine move to the new
  line. Fixtures that record a *provenance* string — a project generated under
  `0.5.0` — are deliberately left alone: they model an input `update` must
  still handle, not the supported range.
- `examples/downstream_cli.py`'s own independently-declared
  `SUPPORTED_ENGINE_RANGE` moves too: its `main()` negotiates against the real
  installed engine, so leaving it stale would make the shipped reference client
  reject the engine this repository now locks. The comment's point — that it
  declares its bounds independently and merely happens to match — is preserved.
- The living contracts that carry the range or the fourteen-component count are
  rewritten in this same change: `docs/integration-contract.md`,
  `docs/engine-updates.md`, `docs/engine-resolution.md`,
  `docs/component-discovery.md`, `docs/engine-contract-tests.md`,
  `docs/end-to-end-tests.md`, `docs/engine-default-cli.md`,
  `docs/project-spec-construction.md`, `docs/filesystem-generation.md`, the
  user guide, and `docs/cross-repository-workflow.md`, which also loses text
  describing the `engine` extra ADR 0040 removed. `docs/roadmap-v4/**` is
  untouched: it is hash-pinned against the filed issue bodies.
- Clients pinned to `create-forge 0.4.0` keep `forge-template>=0.5,<0.6` and
  the stable fourteen-component catalogue; `0.5.x` stays installable under the
  provider's deprecation window.
- `docs/engine-updates.md`'s "Existing generated projects" rule applies as it
  did to the `0.5` crossing. The fourteen existing components are unchanged in
  `0.6.0` (the provider pins a byte-level digest per archetype), and
  `create-forge update` routes engine-generated projects through the
  engine-native path of
  [ADR 0046](0046-engine-native-update-application.md); `pytest -m network`
  and `poe test:e2e` are run against the exact pair before merge, not deferred
  to CI.
- This is **not** the engine-default cutover, which shipped in `0.4.0`
  (CF-ROADMAP-02-EX-03), and adds no FastAPI archetype, deployment platform,
  remote registry or plugin execution.
