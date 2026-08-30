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
in its `0.3.0` release, and this repository's exact development pin moved to
match (CF-08.02, [ADR 0017](adr/0017-cli-application-archetype-exposure.md)),
so both are now real, discoverable, and exposed through the hidden
`--engine-preview` flag's `--archetype` option. The released v0.1.x CLI
remains a thin Copier
wrapper with a bundled registry (`src/create_forge/templates.toml`), calling
Copier directly through `src/create_forge/runner.py`. [CF-06.01](https://github.com/Sandsy09/create-forge/issues/46)
added a construction boundary — `src/create_forge/spec.py` and
`src/create_forge/engine.py`, recorded by
[ADR 0013](adr/0013-projectspec-construction-boundary.md) and the canonical
[ProjectSpec construction contract](project-spec-construction.md) — ahead of
any command calling it; `new` is unchanged. Everything in this document
describes rules that hold once the engine exists, plus what is real today.

## Normal installed resolution

At the CLI cutover, `create-forge` will depend on the engine package the same way it
depends on `copier`, `typer`, or `pydantic` today: a bounded version range in
`pyproject.toml`, resolved by the installer at install time. There is no
runtime fetch — the CLI never clones or downloads executable content to
satisfy normal operation.

| create-forge line | forge-template engine range | ProjectSpec protocol | Status |
| --- | --- | --- | --- |
| v0.1.x | None; direct Copier integration | None | Current released architecture |
| First engine line | *Unassigned* | `1` (defined; not yet supported) | Engine API defined; see "Assigning the first engine range" below |

The distribution channel behind that dependency — a package index, a pinned
VCS revision, or another mechanism — is explicitly out of scope here and is
tracked by [PyPI publishing / #9](https://github.com/Sandsy09/create-forge/issues/9);
[ADR 0012](adr/0012-engine-dependency-update-policy.md) explains why that
question stays with #9 rather than moving to CF-05.02. How a compatible
update to this dependency is *adopted*, once a range exists, is a separate
question answered by the canonical [engine update policy](engine-updates.md).

A development-only dependency exists ahead of that runtime one:
`src/create_forge/engine.py` depends on `forge-template` via a `uv`
dependency group constrained to exact package version `0.3.0` and pinned to
`tag = "v0.3.0"`, not a released version range — see
[ADR 0013](adr/0013-projectspec-construction-boundary.md). This is not the
range assigned below; it exists so the construction boundary can exercise
the real engine before `forge-template` publishes anything installable. The
[cross-repository engine contract tests](engine-contract-tests.md) reject any
other development package version until it is deliberately adopted. This pin
has moved twice: CF-07.04 ([ADR 0015](adr/0015-staged-filesystem-generation.md))
moved it once, within the prior unreleased `0.2.0` contract, to adopt
generated-project validation; CF-08.02
([ADR 0017](adr/0017-cli-application-archetype-exposure.md)) moved it again,
to the first tagged release, adopting a tag over a commit SHA now that one
exists.

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

| Field | Reported today (v0.1.x) | Reported after cutover |
| --- | --- | --- |
| `create_forge` | CLI version | unchanged |
| `python`, `platform` | interpreter version and OS | unchanged |
| `integration.line` | `"v0.1.x-copier"` | the active integration line |
| `integration.copier` | installed Copier version | present while Copier remains a direct dependency |
| `integration.engine_package` | `null` | installed engine package version |
| `integration.engine_range` | `null` | the range this CLI release supports |
| `integration.projectspec_protocol.supported` / `.detected` | `null` / `null` | supported and detected ProjectSpec protocol |
| `integration.template_source` | bundled registry URL | resolved engine/template source |
| `integration.template_ref` | `null` (doctor stays offline; it does not resolve a ref) | resolved template/asset release |

`doctor` performs no network calls. `integration.template_ref` stays `null`
under v0.1.x rather than resolving Copier's "latest PEP 440 tag" at
diagnostic time — that resolution belongs to `scaffold`/`update`, not to a
health check.

## Unsupported combinations

Once an engine dependency exists, an installed or overridden engine package,
or ProjectSpec protocol, outside the supported range must fail closed
*before* component discovery, rendering, template task execution, or any
destination write. The error identifies the detected version, states the
supported range, and gives one concrete remediation. There is no fallback to
the bundled registry or direct Copier.

This failure class uses exit status **`3`**, reserved exclusively for it
(see [`docs/cli-conventions.md`](cli-conventions.md)'s exit-status table).
It does not exist in the v0.1.x line today — nothing in the current
direct-Copier path can raise it — and is documented here as reserved so its
absence from `cli.py` is legible as deliberate rather than an oversight.

The development-only adapter already applies the same ordering to its exact
`0.3.0` pair: package and protocol mismatches fail before parsing, discovery,
validation, or in-memory rendering. This is development-contract evidence,
not a claim that v0.1.x supports an engine package.

## Assigning the first engine range

`forge-template` FT-06.07 defines the `0.2.x` engine API and CF-06.03 proves
the exact development pair described above, but neither action assigns a
released range. After #9 chooses an installable distribution channel, perform
these steps together in CF-07.01's coordinated CLI adoption:

1. Add the engine as a real dependency in `pyproject.toml` with a tested
   lower bound.
2. Apply the upper-bound rule from the
   [integration contract](integration-contract.md#version-and-protocol-compatibility):
   `>=0.y.a,<0.(y+1)` pre-1.0, `>=n.a,<n+1` from 1.0.
3. Fill in the real values in this document's resolution table and in
   `docs/integration-contract.md`'s compatibility table.
4. Replace the exact development assertion with contract and end-to-end tests
   exercising the declared lower bound and a representative latest compatible
   release, per
   the [cross-repository contributor workflow](cross-repository-workflow.md),
   the [engine update policy](engine-updates.md)'s adoption rule, and the
   [ProjectSpec construction contract](project-spec-construction.md)'s
   negotiation and validation rules.
5. Remove `tests/test_engine_contract.py`'s "no runtime engine dependency"
   branch, since it stops being true.

## Executable examples

- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py) —
  guards that no speculative engine range is reserved ahead of a real
  dependency, and that this document stays linked from `CLAUDE.md`,
  `CONTRIBUTING.md`, and the integration contract.
- [`tests/test_cli.py`](../tests/test_cli.py) —
  `test_doctor_reports_versions_and_the_unimplemented_engine`,
  `test_doctor_json_emits_the_documented_shape`, and
  `test_doctor_json_exits_1_when_a_check_fails` characterize the diagnostics
  contract's table and `--json` output, including the engine and
  ProjectSpec-protocol fields staying `null`/absent under v0.1.x.
- [`tests/test_config.py`](../tests/test_config.py) —
  `test_config_cannot_redirect_the_template_source` and
  `test_no_config_field_looks_like_a_source_or_version_selector`
  characterize the "ordinary configuration may never do" rule above.

When a change alters one of the rules above, update this document and its
characterization tests in the same pull request.
