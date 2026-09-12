# Template-Engine Source and Version Resolution

This is the living contributor contract for how `create-forge` obtains,
overrides, diagnoses, and rejects the `forge-template` template engine.
[ADR 0010](adr/0010-public-engine-integration-contract.md) accepted the
public-engine target and the [integration contract](integration-contract.md)
records its compatibility rules; [ADR 0011](adr/0011-engine-source-and-version-resolution.md)
records the resolution decision this document keeps current.

## Status

The public engine is the accepted target architecture, and CF-18.01
([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md)) has
made it the *default* `new` architecture. Strict
[ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
and [component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
are implemented by the
[stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
under [forge-template ADR 0029](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0029-stable-template-engine-api.md).
`forge-template` ships `library`, `cli`, and `data-science` archetypes (plus
the `github` platform and eight tooling capabilities), exposed here (CF-08.02,
[ADR 0017](adr/0017-cli-application-archetype-exposure.md)) through `new`'s
`--archetype` option — visible and default-path, not a hidden flag.

[#9](https://github.com/Sandsy09/create-forge/issues/9) and
[ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md) then
did what "Assigning the first engine range" below used to describe as future
work: `forge-template` published `0.3.1` to PyPI, and this repository
declared its first real, installable, range-bounded engine dependency,
`forge-template>=0.3.1,<0.4` as the optional `engine` extra
(`create-forge[engine]`).
[CF-13.01 / ADR 0026](adr/0026-adopt-the-0-4-engine-compatibility-line.md)
then moved that range to `forge-template>=0.4,<0.5` — the 0.4 line whose
lower bound `0.4.0` first ships the Data Science archetype and reusable
capabilities. [CF-14.01 / ADR 0031](adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md)
adopted the reviewed `forge-template>=0.4.1,<0.5` release as the lower bound
for create-forge `0.3.x`, still the optional `engine` extra. CF-18.01
([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md),
[ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md)) then
adopted the reviewed `forge-template>=0.5,<0.6` engine-default cutover
release as a **required** dependency: `new` with no route flag is now the
engine path, calling `forge-template` directly through
`src/create_forge/engine.py`; `copier` moved into the optional `legacy`
extra, reached through `new --legacy` (thin Copier wrapper, bundled
registry, `src/create_forge/runner.py`, unchanged). The full cutover this
document otherwise describes — `--engine-source`/`--engine-ref` alongside a
retained `--template-url` under `--legacy` — remains
[CF-18.02](https://github.com/Sandsy09/create-forge/issues/159)'s, part of
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153).

`forge-template 0.5.0` is the lower bound of the current line and its current
compatible release — the first to publish `metadata_version` and
component-manifest protocol `3`. `create-forge 0.2.1` added
`uv>=0.12,<0.13` to the same dependency set so the client can create the
engine-generated project's lock before finalisation; it is now required
alongside the engine rather than bundled in its extra.

Adopting the 0.5 line keeps the Data Science components discoverable through
`--archetype data-science`. CF-13.02
([ADR 0027](adr/0027-generic-component-selection-conventions.md)) fixed the
conventions for selecting them — capabilities, platforms, component options —
in the canonical [component selection contract](component-selection.md);
CF-13.03 ([ADR 0028](adr/0028-discovery-driven-component-selection.md)) and
CF-13.04 ([ADR 0029](adr/0029-per-component-option-collection.md)) implemented
it, and CF-13.05
([ADR 0030](adr/0030-data-science-preview-pipeline-validation.md)) proved the
Data Science composition traverses the shared pipeline against the released
engine. Normal
resolution now rejects any engine below `0.5.0` or at/above `0.6.0`, and later
`0.5.x` releases inside the range are adopted per the canonical
[engine update policy](engine-updates.md).

## Normal installed resolution

`create-forge` depends on the engine package the same way it depends
on `typer` or `pydantic`: a bounded version range in
`pyproject.toml`, resolved by the installer at install time. There is no
runtime fetch — the CLI never clones or downloads executable content to
satisfy normal operation. It is a required `[project.dependencies]` entry
since CF-18.01 (ADR 0040 decision 1): a plain `pip install create-forge` /
`uvx create-forge` resolves it, so the default `new` path always has it.
`copier` is the one now behind an extra — `pip install 'create-forge[legacy]'`
or `uv sync --all-extras` — for `new --legacy` and `update`'s Copier route.

| create-forge line | forge-template engine range | ProjectSpec protocol | Status |
| --- | --- | --- | --- |
| v0.1.x | None; direct Copier integration | None | Superseded by v0.2.x |
| v0.2.x (`engine` extra) | `forge-template>=0.3.1,<0.4` | `1` (supported) | Superseded by v0.3.x (ADR 0018) |
| v0.3.x (`engine` extra) | `forge-template>=0.4.1,<0.5` | `1` (supported) | Superseded by v0.4.x (ADR 0042) |
| v0.4.x (required) | `forge-template>=0.5,<0.6` | `1` (supported) | Current architecture (ADR 0042, CF-18.01) |

The distribution channel is PyPI, via Trusted Publishing (OIDC) on both
repositories' `release.yml` workflows —
[forge-template ADR 0036](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0036-publish-the-engine-to-pypi.md)
and [ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md).
How a compatible update to this dependency is *adopted* going forward is a
separate question, answered by the canonical
[engine update policy](engine-updates.md) — pre-1.0, a `forge-template` minor
bump is itself a new compatibility line, exactly like a Copier major.

A separate development-only override still exists ahead of ordinary
resolution: cross-repository work on an unreleased `forge-template` checkout
uses `[tool.uv.sources]` locally (never committed) or the sibling-checkout
command in the
[cross-repository contributor workflow](cross-repository-workflow.md) — see
[ADR 0013](adr/0013-projectspec-construction-boundary.md). This is
workspace-local `uv` configuration, not a `pyproject.toml` dependency
declaration, and does not change the range in the table above.

## Local development resolution

Cross-repository development needs to point `create-forge` at an unreleased
`forge-template` checkout. ADR 0011 names the interface that will do this at
the engine cutover: `--engine-source <path|vcs-url>` plus `--engine-ref
<ref>` (valid only alongside `--engine-source`). It always prints the
code-execution warning; `--yes` skips the confirmation but not the warning.
Content resolved this way must pass the same compatibility check as an
installed engine before anything renders.

The engine-default cutover contract
([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md),
[`docs/engine-default-cli.md`](engine-default-cli.md)) fixes the mechanism ADR
0011 left open: `--engine-source` provisions the named path or VCS URL — with
an optional `--engine-ref` — into an **isolated ephemeral environment** with
`uv`, and the whole generation runs against that engine. The installed engine
is never imported, shadowed or modified, and there is no in-process `sys.path`
injection. Source validation is `--template-url`'s
([ADR 0036](adr/0036-template-source-credentials.md)). A render produced this
way writes **no generation-metadata document** — that document fixes
`provider.distribution` to `forge-template` and admits no source string — so
an `--engine-source` project is not `create-forge update`-able, and its
post-generation message says so.

`--engine-source`/`--engine-ref` select an engine *distribution*; they are
orthogonal to the retained `--template-url`/`--ref`, which CF-18.01 scoped to
the explicit `--legacy` Copier route rather than replacing them (ADR 0040
supersedes ADR 0011's "no dual direct-Copier path afterward" clause only).

**These flags do not exist yet.** Until
[CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) implements
them, the sanctioned development path is `--legacy`'s `--template-url`,
exactly as [`docs/cross-repository-workflow.md`](cross-repository-workflow.md)
describes:

```bash
uv run create-forge new --legacy "Cross Repo Smoke" --yes \
  --template-url ../forge-template --ref HEAD \
  --path ../create-forge-cross-repo-smoke \
  --data github_org=test-org --data "author_name=Test User" \
  --data author_email=test@example.invalid
```

## What ordinary configuration may never do

`config.toml` and `FORGE_*` environment variables (`src/create_forge/config.py`)
remain answer-preset conveniences only. Neither gains a source, engine,
range, or protocol field: `UserConfig`'s `extra="forbid"` model configuration
turns an attempt to add one into a validation error rather than a silent new
capability (`tests/test_config.py::test_config_cannot_redirect_the_template_source`).
A generated project's own recorded engine version lives in that project's
own engine-owned answers file and is never promoted into CLI-wide config.

## Diagnostics contract

`create-forge doctor` must expose enough version information to reproduce a
compatibility failure, in both its table and its `--json` output
(`create-forge doctor --json`). The fields below are stable; new fields may
be added, but existing ones do not change meaning or disappear before a
major version.

| Field | Reported | Populated by |
| --- | --- | --- |
| `create_forge` | CLI version | always |
| `python`, `platform` | interpreter version and OS | always |
| `integration.line` | `"v0.3.x-engine"` | always — the CLI release line and default generation architecture; a fast regression test compares its major/minor with `pyproject.toml`'s own version |
| `integration.copier` | installed Copier version, `null` if the `legacy` extra isn't installed | `importlib.metadata`, never an import of Copier itself |
| `integration.engine_package` | installed `forge-template` version, `null` only in a broken install | `importlib.metadata`, and a real check: a missing engine fails closed at exit `1`, since it is a required dependency (ADR 0040 decision 1) |
| `integration.engine_range` | `"forge-template>=0.5,<0.6"` | always -- this is what this CLI release declares, independent of what's installed |
| `integration.projectspec_protocol.supported` | `"1"` | always, from `src/create_forge/compat.py` |
| `integration.projectspec_protocol.detected` | the installed engine's advertised tuple, joined by commas | via a real `engine.get_info()` call whenever `engine_package` is not `null` -- see below |
| `integration.component_manifest_protocol.supported` | `"1,2,3"` | always, from `src/create_forge/compat.py` |
| `integration.component_manifest_protocol.detected` | the installed engine's advertised tuple | same negotiation as `projectspec_protocol.detected` |
| `integration.metadata_version.supported` | `"1"` | always, from `src/create_forge/compat.py` |
| `integration.metadata_version.detected` | the installed engine's advertised value | same negotiation |
| `integration.template_source` | bundled registry URL | always |
| `integration.template_ref` | `null` (doctor stays offline; it does not resolve a ref) | never |
| `copier_cache.path` | Copier's resolved git-mirror cache directory, or an informational "not applicable" row when the `legacy` extra is absent | `runner.copier_cache_location()` — Copier's documented `COPIER_CACHE_DIR`-else-platformdirs rule ([ADR 0039](adr/0039-copier-cache-diagnostics.md)) |
| `copier_cache.override` | `true` when `COPIER_CACHE_DIR` selected the path | when the `legacy` extra is installed |
| `copier_cache.exists` | whether that directory exists yet | when the `legacy` extra is installed |
| `copier_cache.writable` | whether create-forge could write there (or into its deepest existing ancestor) without creating or altering it | when the `legacy` extra is installed — the one field that can fail a check and set `ok` to `false` |
| `uv.path` | `shutil.which("uv")` — the binary `staging.create_uv_lock` would run | always, `null` when `uv` is not on `PATH` |
| `uv.version` | the version token parsed from `uv --version`, or `null` if it can't be trusted | always; a subprocess, never a network call |
| `uv.package` | the (now required) `uv` distribution version | `importlib.metadata`, `null` only in a broken install |

`doctor` performs no network calls. Engine presence and the declared range
are read via `importlib.metadata` and `src/create_forge/compat.py` alone,
both engine-free by construction (`tests/test_engine_contract.py`'s
`_SHIPPED_MODULES` guard covers `compat.py` for exactly this reason). Since
ADR 0040 decision 6 (CF-18.01), `doctor` additionally calls
`engine.get_info()` — a real negotiation, still offline and still no
destination write — whenever the engine package is installed, populating
every `*.detected` field above and reporting a protocol/`metadata_version`
mismatch as one failed check that fails `ok` (exit `1`), rather than raising
`EngineCompatibilityError` and crashing `doctor` outright. `integration.copier`
and the `copier_cache.*` fields become `null`/informational when the
`legacy` extra is absent, since `copier` moved there at the same cutover.
`integration.template_ref` stays `null` for the same "no network, no
cutover-scoped work" reason -- that resolution belongs to `scaffold`/`update`,
not to a health check.

The human table reports `integration line` as the same informational value.
It is not a health check and cannot change the exit status. The explicit value
lives in engine-free `compat.py`; a fast regression test compares its major and
minor components with `pyproject.toml`, so a future release-line change must
review the identifier deliberately while patch releases leave it unchanged.

The `copier_cache.writable` probe is non-destructive: it writes and deletes one
uniquely named file in the cache directory, or -- when that directory does not
exist yet -- in its deepest existing ancestor, which is what Copier's own
`mirror.parent.mkdir(parents=True)` writes into. It never creates the cache
directory and never reads, writes, or lists a `<sha>.git` mirror. `os.access`
is deliberately not used: on Windows it ignores ACLs and reports a locked-down
corporate cache directory as writable, the exact condition the probe exists to
catch ([ADR 0039](adr/0039-copier-cache-diagnostics.md)).

## Unsupported combinations

An installed or overridden engine package, or ProjectSpec protocol, outside
the supported range fails closed *before* component discovery, rendering,
template task execution, or any destination write. The error identifies the
detected version, states the supported range, and gives one concrete
remediation. There is no fallback to the bundled registry or direct Copier.

This failure class uses exit status **`3`**, reserved exclusively for it
(see [`docs/cli-conventions.md`](cli-conventions.md)'s exit-status table).
It is reachable on the now-default `new` path, since the engine is what it
calls unconditionally. ADR 0040 decision 12 (CF-18.01) widened what `3`
covers -- an engine that cannot be imported at all, an out-of-range
component-manifest protocol or `metadata_version`, and `--legacy` without the
`legacy` extra installed -- keeping one status for "the required generator is
missing or unusable" with no silent fallback.

`src/create_forge/engine.py` applies this ordering against the range in the
table above: package and protocol mismatches fail before parsing, discovery,
validation, or in-memory rendering, checked with
`packaging.specifiers.SpecifierSet` rather than the exact-equality check the
Stage 06 development contract used before a real release existed.

## Executable examples

- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py) --
  guards that the engine dependency is declared exactly as a required
  dependency, at the range this document's table states, and that this
  document stays linked from `CLAUDE.md`, `CONTRIBUTING.md`, and the
  integration contract.
- [`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py) --
  `test_negotiate_protocol_rejects_a_package_outside_the_supported_range`
  characterizes both edges of the range (below the lower bound, at the
  excluded upper bound) against the real installed engine.
- [`tests/test_cli.py`](../tests/test_cli.py) --
  `test_doctor_fails_when_the_engine_is_not_installed`,
  `test_doctor_reports_the_installed_engine_package_when_present`, and
  `test_doctor_json_emits_the_documented_shape` characterize the diagnostics
  contract's table and `--json` output above, including `engine_package`
  failing the check when absent and every `*.detected` field being populated
  by a real negotiation against the installed engine.
  `test_doctor_reports_the_copier_cache_and_uv` and
  `test_doctor_fails_when_the_copier_cache_is_unwritable` cover the
  `copier_cache.*` / `uv.*` objects and the unwritable-cache check flipping
  `ok` to `false`.
- [`tests/test_copier_cache.py`](../tests/test_copier_cache.py)
  ([ADR 0039](adr/0039-copier-cache-diagnostics.md)) -- pins
  `runner.copier_cache_location()` to Copier's own `copier._vcs._get_cache_dir`
  under both the default and `COPIER_CACHE_DIR` branches, and characterizes
  the non-destructive writability probe (missing directory, denied directory,
  contents left untouched).
- [`tests/test_config.py`](../tests/test_config.py) --
  `test_config_cannot_redirect_the_template_source` and
  `test_no_config_field_looks_like_a_source_or_version_selector`
  characterize the "ordinary configuration may never do" rule above.
- [`tests/test_e2e_installed_rollout.py`](../tests/test_e2e_installed_rollout.py)
  (CF-14.03, [ADR 0033](adr/0033-complete-rollout-regression-validation.md)) --
  `test_engineless_doctor_json_reports_the_absent_engine` and
  `test_out_of_range_engine_is_visible_in_doctor` characterize the diagnostics
  table's `engine_package` against the *installed* release candidate with, in
  turn, no engine and a real out-of-range engine resolved.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
