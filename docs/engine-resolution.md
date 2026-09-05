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
document otherwise describes — the engine replacing direct Copier as the
default, `--engine-source`/`--engine-ref` replacing `--template-url` — is
still a future, unfiled decision.

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

**These flags do not exist yet.** Until the cutover, the sanctioned
development path is today's `--template-url`, exactly as
[`docs/cross-repository-workflow.md`](cross-repository-workflow.md)
describes:

```bash
uv run create-forge new "Cross Repo Smoke" --yes \
  --template-url ../forge-template --ref HEAD \
  --path ../create-forge-cross-repo-smoke \
  --data github_org=test-org --data "author_name=Test User" \
  --data author_email=test@example.invalid
```

At cutover, this predecessor option is replaced in the same atomic release —
there is no dual direct-Copier and engine-override path afterward.

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
| `integration.line` | `"v0.2.x-copier"` | always |
| `integration.copier` | installed Copier version | always -- Copier remains a direct dependency |
| `integration.engine_package` | installed `forge-template` version, `null` if the `engine` extra isn't installed | `importlib.metadata`, never an import of the engine itself |
| `integration.engine_range` | `"forge-template>=0.4.1,<0.5"` | always -- this is what this CLI release declares, independent of what's installed |
| `integration.projectspec_protocol.supported` | `"1"` | always, from `src/create_forge/compat.py` |
| `integration.projectspec_protocol.detected` | `null` | never by `doctor` -- see below |
| `integration.template_source` | bundled registry URL | always |
| `integration.template_ref` | `null` (doctor stays offline; it does not resolve a ref) | never |

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

## Unsupported combinations

An installed or overridden engine package, or ProjectSpec protocol, outside
the supported range fails closed *before* component discovery, rendering,
template task execution, or any destination write. The error identifies the
detected version, states the supported range, and gives one concrete
remediation. There is no fallback to the bundled registry or direct Copier.

This failure class uses exit status **`3`**, reserved exclusively for it
(see [`docs/cli-conventions.md`](cli-conventions.md)'s exit-status table).
It is reachable today only via `--engine-preview` -- the default `new` path
still cannot raise it, since it never touches the engine at all.

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
- [`tests/test_config.py`](../tests/test_config.py) --
  `test_config_cannot_redirect_the_template_source` and
  `test_no_config_field_looks_like_a_source_or_version_selector`
  characterize the "ordinary configuration may never do" rule above.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
