# Template-Engine Source and Version Resolution

This is the living contributor contract for how `create-forge` obtains,
overrides, diagnoses, and rejects the `forge-template` template engine.
[ADR 0010](adr/0010-public-engine-integration-contract.md) accepted the
public-engine target and the [integration contract](integration-contract.md)
records its compatibility rules; [ADR 0011](adr/0011-engine-source-and-version-resolution.md)
records the resolution decision this document keeps current. Like
[`docs/cli-conventions.md`](cli-conventions.md), this file is expected to
change as the engine cutover approaches — the *rules* below are the
contract; today's mechanisms are not.

## Status

The public engine is the accepted target architecture. Strict
[ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
and [component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
are implemented by the
[stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
under [forge-template ADR 0029](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0029-stable-template-engine-api.md).
`forge-template` ships both Library and the
[CLI Application archetype](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
as of its `0.3.0` release, exposed here (CF-08.02,
[ADR 0017](adr/0017-cli-application-archetype-exposure.md)) through the
hidden `--engine-preview` flag's `--archetype` option.

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
adopts the reviewed `forge-template>=0.4.1,<0.5` release as the lower bound
for create-forge `0.3.x`. **This is not yet the CLI cutover.** The released default `new`
command remains a thin Copier wrapper with a bundled registry
(`src/create_forge/templates.toml`), calling Copier directly through
`src/create_forge/runner.py`. The engine range below is reachable only
through `--engine-preview`; nothing about the default path, its
`--template-url` escape hatch, or `--ref` changed. The full cutover this
document otherwise describes — the engine as the default `new` path, with
`--engine-source`/`--engine-ref` alongside a retained `--template-url` — is
the subject of
[CF-EPIC-16](https://github.com/Sandsy09/create-forge/issues/152); its
selection and source-resolution UX is fixed by
[ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md) and
[`docs/engine-default-cli.md`](engine-default-cli.md), and implemented by
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153), none of
which has shipped.

`forge-template 0.4.1` is the lower bound of the current line and its current
compatible release. It republishes the reviewed `0.4.0` production source and
rendered bytes unchanged, so the adoption changes no protocol. `create-forge 0.2.1` adds
`uv>=0.12,<0.13` to the same optional extra so the client can create the
engine-generated project's lock before finalisation.

Adopting the 0.4 line makes the Data Science components discoverable through
`--engine-preview`. CF-13.02
([ADR 0027](adr/0027-generic-component-selection-conventions.md)) fixed the
conventions for selecting them — capabilities, platforms, component options —
in the canonical [component selection contract](component-selection.md);
CF-13.03 ([ADR 0028](adr/0028-discovery-driven-component-selection.md)) and
CF-13.04 ([ADR 0029](adr/0029-per-component-option-collection.md)) implemented
it, and CF-13.05
([ADR 0030](adr/0030-data-science-preview-pipeline-validation.md)) proved the
Data Science composition traverses the shared pipeline against the released
engine. Normal
resolution now rejects any engine below `0.4.1`, and later `0.4.x` releases
inside the range are adopted per the canonical [engine update policy](engine-updates.md).

## Normal installed resolution

`create-forge[engine]` depends on the engine package the same way it depends
on `copier`, `typer`, or `pydantic`: a bounded version range in
`pyproject.toml`, resolved by the installer at install time. There is no
runtime fetch — the CLI never clones or downloads executable content to
satisfy normal operation. Because it is an optional extra rather than a
`[project.dependencies]` entry, installing plain `create-forge` (the default
`new` path) never resolves it at all; only `pip install 'create-forge[engine]'`
or `uv sync --all-extras` does, matching ADR 0014's guarded
`try/except ImportError` in `cli.py`.

| create-forge line | forge-template engine range | ProjectSpec protocol | Status |
| --- | --- | --- | --- |
| v0.1.x | None; direct Copier integration | None | Superseded by v0.2.x |
| v0.2.x (`engine` extra) | `forge-template>=0.3.1,<0.4` | `1` (supported) | Superseded by v0.3.x (ADR 0018) |
| v0.3.x (`engine` extra) | `forge-template>=0.4.1,<0.5` | `1` (supported) | Current architecture (ADR 0031) |

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
orthogonal to the retained `--template-url`/`--ref`, which stay scoped to the
`--legacy` Copier route rather than being replaced (ADR 0040 supersedes ADR
0011's "no dual direct-Copier path afterward" clause only —
[CF-16.01 / #155](https://github.com/Sandsy09/create-forge/issues/155),
a Stage 16 contract, not yet implemented).

**These flags do not exist yet.** Until the cutover,
[CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) implements
them, and the sanctioned development path is today's `--template-url`, exactly
as [`docs/cross-repository-workflow.md`](cross-repository-workflow.md)
describes:

```bash
uv run create-forge new "Cross Repo Smoke" --yes \
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
| `integration.line` | `"v0.3.x-copier"` | always — the CLI release line and default generation architecture; installing the engine extra does not change it |
| `integration.copier` | installed Copier version | always -- Copier remains a direct dependency |
| `integration.engine_package` | installed `forge-template` version, `null` if the `engine` extra isn't installed | `importlib.metadata`, never an import of the engine itself |
| `integration.engine_range` | `"forge-template>=0.4.1,<0.5"` | always -- this is what this CLI release declares, independent of what's installed |
| `integration.projectspec_protocol.supported` | `"1"` | always, from `src/create_forge/compat.py` |
| `integration.projectspec_protocol.detected` | `null` | never by `doctor` -- see below |
| `integration.template_source` | bundled registry URL | always |
| `integration.template_ref` | `null` (doctor stays offline; it does not resolve a ref) | never |
| `copier_cache.path` | Copier's resolved git-mirror cache directory | always, from `runner.copier_cache_location()` — Copier's documented `COPIER_CACHE_DIR`-else-platformdirs rule ([ADR 0039](adr/0039-copier-cache-diagnostics.md)) |
| `copier_cache.override` | `true` when `COPIER_CACHE_DIR` selected the path | always |
| `copier_cache.exists` | whether that directory exists yet | always |
| `copier_cache.writable` | whether create-forge could write there (or into its deepest existing ancestor) without creating or altering it | always — the one new field that can fail a check and set `ok` to `false` |
| `uv.path` | `shutil.which("uv")` — the binary `staging.create_uv_lock` would run | always, `null` when `uv` is not on `PATH` |
| `uv.version` | the version token parsed from `uv --version`, or `null` if it can't be trusted | always; a subprocess, never a network call |
| `uv.package` | the `engine` extra's declared `uv` distribution version | `importlib.metadata`, `null` when the extra isn't installed — a distinct fact from `uv.path` |

`doctor` performs no network calls and, deliberately, no engine import: it
reads `engine_package`/`engine_range`/`projectspec_protocol.supported` via
`importlib.metadata` and `src/create_forge/compat.py` alone, both engine-free
by construction (`tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard
covers `compat.py` for exactly this reason). `projectspec_protocol.detected`
therefore stays `null` even with the engine installed -- populating it needs
a real `get_engine_info()` call, which only `--engine-preview` makes.
`integration.template_ref` stays `null` for the same "no network, no
cutover-scoped work" reason -- that resolution belongs to `scaffold`/`update`,
not to a health check.

The human table reports `integration line` as the same informational value.
It is not a health check and cannot change the exit status. The explicit value
lives in engine-free `compat.py`; a fast regression test compares its major and
minor components with `pyproject.toml`, so a future release-line change must
review the identifier deliberately while patch releases leave it unchanged.
The corrected `v0.3.x-copier` value is unreleased and will first appear in an
installed package with the next create-forge release after `0.3.2`.

At the engine-default cutover
([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md),
[`docs/engine-default-cli.md`](engine-default-cli.md)) `doctor` starts
negotiating against the real engine: it calls `get_engine_info()` — still
offline, still no destination write — and populates
`projectspec_protocol.detected`, the component-manifest protocol tuple and
`metadata_version`, reporting a mismatch as a failed check that exits `1`.
`integration.copier` becomes `null` when the `legacy` extra is absent,
`integration.engine_package` becomes a required field, and `integration.line`
takes an identifier of the form `v<major>.<minor>.x-engine`. `compat.py` stays
engine-free; the `get_engine_info()` call lives in `engine.py`. This is a
Stage 16 contract ([CF-16.01 / #155](https://github.com/Sandsy09/create-forge/issues/155)),
implemented by [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158),
not yet shipped.

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
It is reachable today only via `--engine-preview` -- the default `new` path
still cannot raise it, since it never touches the engine at all. The
engine-default cutover contract
([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md))
widens what `3` covers -- an engine that cannot be imported at all, an
out-of-range component-manifest protocol or `metadata_version`, and `--legacy`
without the `legacy` extra -- keeping one status for "the required generator
is missing or unusable" with no silent fallback.

`src/create_forge/engine.py` applies this ordering against the range in the
table above: package and protocol mismatches fail before parsing, discovery,
validation, or in-memory rendering, checked with
`packaging.specifiers.SpecifierSet` rather than the exact-equality check the
Stage 06 development contract used before a real release existed.

## Executable examples

- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py) --
  guards that the engine dependency is declared exactly as the optional
  `engine` extra, at the range this document's table states, and that this
  document stays linked from `CLAUDE.md`, `CONTRIBUTING.md`, and the
  integration contract.
- [`tests/test_engine_adapter.py`](../tests/test_engine_adapter.py) --
  `test_negotiate_protocol_rejects_a_package_outside_the_supported_range`
  characterizes both edges of the range (below the lower bound, at the
  excluded upper bound) against the real installed engine.
- [`tests/test_cli.py`](../tests/test_cli.py) --
  `test_doctor_reports_versions_and_the_engine_range`,
  `test_doctor_json_emits_the_documented_shape`, and
  `test_doctor_json_exits_1_when_a_check_fails` characterize the diagnostics
  contract's table and `--json` output above, including `engine_package`
  and `projectspec_protocol.detected` staying `null` when the extra isn't
  installed or doctor hasn't negotiated, respectively.
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
