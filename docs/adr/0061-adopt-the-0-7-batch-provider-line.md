# 61. Adopt the forge-template 0.7 batch provider line

## Status

Accepted

## Context

[Issue #204 / CF-29.01](https://github.com/Sandsy09/create-forge/issues/204)
is the first child of
[CF-EPIC-29](https://github.com/Sandsy09/create-forge/issues/192), which
adopts the Pipeline/Batch Job archetype in the client. Its blocker,
[FT-28.03](https://github.com/Sandsy09/forge-template/issues/203), closed on
2026-10-06 with the publication of
[`forge-template 0.7.0`](https://github.com/Sandsy09/forge-template/releases/tag/v0.7.0)
to [PyPI](https://pypi.org/project/forge-template/0.7.0/) at commit
`8d12452cfdc9bcae942d885a6ba93587130d8d26` — an immutable provider release, not
a moving branch. The artefact hashes the provider recorded
(wheel `sha256:edaf0604…`, sdist `sha256:7d0e2364…`) are the ones `uv.lock` now
carries.

[ADR 0050](0050-adopt-the-0-6-streamlit-provider-line.md) assigned the
`forge-template>=0.6,<0.7` range that published `create-forge 0.5.0` declares.
Under [ADR 0012](0012-engine-dependency-update-policy.md), a pre-1.0 minor bump
is itself a new compatibility line: Dependabot is barred from proposing it, and
adopting it is a deliberate, human-authored change that moves the declared
bound, the depending code, and every compatibility table together. Until that
change, normal resolution must keep rejecting `0.7.0` — and `create-forge
0.5.0` does, with exit status `3` before any destination write.

The evidence is measured on the provider's tags rather than taken from its
prose. Over `v0.6.0..v0.7.0` in `forge-template`:

- `git diff` over the public facade (`__init__.py`) is empty;
- `pyproject.toml` changes its version, task metadata and the *test* group's
  Copier floor, but no runtime dependency and not `requires-python`;
- `copier.yml` asks the same questions (invariant 1 is unaffected), raises
  `_min_copier_version` to `9.6.0`, and makes its git and hook `_tasks`
  copy-only — the `legacy` extra already requires `copier>=9.16`;
- the new `components/batch/` tree is the only catalogue change, and
  `engine.py` was split into private modules behind the frozen facade, which
  moves no signature this client calls.

The installed `0.7.0` reports ProjectSpec protocol `(1,)`, component-manifest
protocols `(1, 2, 3)` and `metadata_version` `1` — all unchanged — and
`discover_components()` returns sixteen descriptors instead of fifteen. The one
addition is `batch`: an archetype at component version `1.0.0`, manifest
protocol `2`, that declares no `requires`, `conflicts` or options, so it is
catalogue data behind an unchanged facade.

The provider's hand-off also recorded a client-side gap. `create-forge doctor`'s
`engine` check passed on presence alone (`importlib.metadata` found a
`forge-template`), never on range, so `doctor --json` reported `ok: true` for an
out-of-range `0.7.0` while `new` refused the same engine at exit `3`. That gap
predates this line; the line merely made a real out-of-range release available
to notice it.

## Decision

1. **Move the declared range to `forge-template>=0.7,<0.8`.**
   `src/create_forge/compat.py`'s `SUPPORTED_ENGINE_RANGE` and
   `pyproject.toml`'s `[project.dependencies]` entry change together, and
   `uv.lock` is regenerated so the committed lock resolves `0.7.0`. The lock
   diff is the `forge-template` package alone. `engine.py`, `engine_source.py`,
   `_engine_worker.py`, `spec.py` and `pipeline.py` need no edit — every range
   and protocol string they emit is interpolated from `compat`.

2. **Leave every protocol tuple unchanged.**
   `SUPPORTED_PROJECTSPEC_PROTOCOLS` stays `(1,)`,
   `SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS` stays `(1, 2, 3)` and
   `SUPPORTED_GENERATION_METADATA_VERSIONS` stays `(1,)`. The zero-diff public
   facade is the evidence: this is a range move, not a protocol migration.

3. **Select `batch` only through the generic contract.** No production module
   names `batch` to decide catalogue, validation, composition or generated
   content behaviour (CF-ROADMAP-02-AC-03). The proof is executable:
   `tests/test_archetype_parity.py`'s parametrisation over every discovered
   archetype now covers a fifth archetype without an edit; a named tripwire
   asserts `batch` is discovered as an optionless archetype; and a guard walks
   *every* module under `src/create_forge` for a `batch` string literal,
   beside the existing `streamlit` one. The new `tests/test_batch_adoption.py`
   drives a real non-interactive (`--archetype batch --yes`) and a real
   interactive `new` through staging and finalisation, and an undeclared
   `--component-option` against `batch` through the engine's own verdict.

4. **Make `doctor` apply the range it reports.** `doctor`'s `engine` check
   fails when the installed version is outside `SUPPORTED_ENGINE_RANGE`, by
   calling `compat.require_supported_package` — the one check `new` applies —
   rather than a second `SpecifierSet`. A failing `engine` row sets `ok` to
   `false` and exits `1`; `new` keeps exit `3`, the status reserved for an
   unusable generator. Negotiation still runs and is reported alongside, so the
   `*_detected` protocol facts stay populated and the failure is attributable
   to the package range alone. No `doctor --json` field is added, renamed or
   removed; only the `engine` check's `ok`, and therefore the top-level `ok`
   and exit status, change for an out-of-range engine.

5. **Accept the provider's archetype order in the interactive prompt.**
   `batch` sorts first in discovery, and `choose_archetype` has no default, so
   the "What are you building?" cursor now starts on "Batch Job" instead of the
   previous first archetype. Discovery order is provider-owned and the generic
   contract makes no ordering promise, so the client does not reorder the list
   or add a default archetype — either would be archetype-specific policy
   (CF-ROADMAP-02-AC-03). `--yes` is unaffected: it already requires
   `--archetype`. `tests/test_batch_adoption.py` pins the offered ids to the
   discovered archetypes, in order, without naming a default.

6. **Do not expose `batch` through the Copier registry.** `templates.toml`
   stays Library-only. The default engine path reaches `batch`; `--legacy`
   never does (CF-ROADMAP-02-EX-01).

7. **Record the line on the `v0.5.x` row, not a new one.** The published
   `create-forge 0.5.0` wheel genuinely declares `>=0.6,<0.7`, but
   `pyproject.toml`'s version stays `0.5.0` — the release version belongs to
   CF-29.03 ([ADR 0009](0009-pyproject-as-the-single-version-source.md)) — and
   `INTEGRATION_LINE` is deliberately tied to that version's major and minor.
   So `docs/integration-contract.md`'s compatibility table (the single
   canonical record, per [ADR 0012](0012-engine-dependency-update-policy.md))
   moves the `v0.5.x` row to the new range and records in its Status cell that
   the range is unreleased and the published `0.5.0` declares the previous one,
   as [ADR 0050](0050-adopt-the-0-6-streamlit-provider-line.md) did for
   `v0.4.x`.

8. **Keep the Dependabot gate as it is.** `.github/dependabot.yml` already
   ignores both `semver-major` and `semver-minor` for `forge-template` by
   dependency name, and `tests/test_engine_contract.py`'s pre-1.0 detection
   still matches `>=0.7`, so the gate stays armed against the `0.8` line.

9. **Prove the previous line is rejected.** The out-of-range fixtures in
   `tests/test_engine_adapter.py`, `tests/test_engine_cross_repository.py` and
   `tests/test_data_science_pipeline.py` gain `0.6.0` — the previous line's
   release, which a client must no longer silently accept — and move the
   excluded-upper-bound case to `0.8.0`, because `0.7.0` is now in range.
   Together they assert the rejection, that no public engine call runs before
   it, and that a rejected `new` writes nothing.

This decision does not choose the next `create-forge` version, release
anything, or validate installed batch generation, lock restoration or the
bounded example job. Those are CF-29.03 and CF-29.02 respectively. It also
leaves the user guide naming the released `>=0.6,<0.7` range: the docs site
deploys from `main`, and published `create-forge 0.5.0` rejects `0.7.0`, so
changing it now would break the documented install until CF-29.03 releases.

## Consequences

- `create-forge doctor` and `doctor --json` report `forge-template>=0.7,<0.8`.
  An installed engine outside it — including the previous `0.6.x` line — now
  fails `doctor` at exit `1` and still fails `new` closed with exit status `3`
  before any destination write.
- `tests/test_engine_contract.py`'s `ENGINE_REQUIREMENT` constant, the
  installed-candidate e2e pin `tests/installed_client.py`'s `ENGINE_VERSION`,
  and the fixtures modelling the currently supported engine move to the new
  line. Fixtures that record a *provenance* string — a project generated under
  `0.6.0` — or use a version as opaque rendered data are deliberately left
  alone: they model an input `update` must still handle, not the supported
  range.
- `examples/downstream_cli.py`'s own independently-declared
  `SUPPORTED_ENGINE_RANGE` moves too: its `main()` negotiates against the real
  installed engine, so leaving it stale would make the shipped reference client
  reject the engine this repository now locks.
- The living contracts that carry the range or the fifteen-component count are
  rewritten in this same change: `docs/integration-contract.md`,
  `docs/engine-updates.md`, `docs/engine-resolution.md` (including the
  diagnostics contract's account of `doctor`'s `engine` row),
  `docs/component-discovery.md`, `docs/engine-contract-tests.md`,
  `docs/end-to-end-tests.md`, `docs/engine-default-cli.md`,
  `docs/project-spec-construction.md` and `docs/cross-repository-workflow.md`.
  The user guide, `docs/roadmap-v*/**` (hash-pinned against the filed issue
  bodies) and the dated validation records of published releases are untouched.
- Clients pinned to `create-forge 0.5.0` keep `forge-template>=0.6,<0.7` and
  the stable fifteen-component catalogue; `0.6.x` stays installable under the
  provider's deprecation window.
- `docs/engine-updates.md`'s "Existing generated projects" rule applies as it
  did to the earlier crossings. The fifteen existing components are unchanged
  in `0.7.0`, and `create-forge update` routes engine-generated projects through
  the engine-native path of
  [ADR 0046](0046-engine-native-update-application.md); `pytest -m network` and
  `poe test:e2e` are run against the exact pair before merge, not deferred to
  CI. The byte-identical comparison of a released client against the provider
  across the two lines cannot be made on the `0.6` pair, so it moves to CF-29.02.
- This is **not** a release, a protocol change, an engine-default switch, or a
  new product feature, and adds no remote registry or plugin execution.
