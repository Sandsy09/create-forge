# CLAUDE.md — create-forge

Guidance for Claude Code working in this repository.

## What this is

`create-forge` is a CLI that scaffolds Python projects from Copier templates,
analogous to `pnpm create-payload-app`. It is a **thin wrapper**: Copier does the
rendering and merging, this tool owns the prompt experience and a bundled
registry of known templates.

Distributed via `uvx create-forge`, and since #9
([ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md))
published to PyPI as `create-forge` (`pip install create-forge`, or
`create-forge[engine]` for the hidden `--engine-preview` path). Public, MIT,
intended for open-source use.

## Repository relationship

Two repositories, deliberately separate:

| Repo | Role |
| --- | --- |
| `https://github.com/Sandsy09/create-forge` | This repo. The CLI. |
| `https://github.com/Sandsy09/forge-template` | The templates it scaffolds from. |

They are split because Copier resolves template versions from PEP440 git tags in
the template repo. A shared repo would make `v1.3.0` ambiguous between the two
codebases. **Do not merge them.** See
[ADR 0003](docs/adr/0003-two-repo-split.md).

## Architecture

```
src/create_forge/
├── models.py       Pydantic v2 models for the registry. No I/O.
├── templates.toml  Bundled registry data. Package data, ships in the wheel.
├── registry.py     Loads + validates templates.toml. Cached.
├── config.py       User config (~/.config/create-forge/config.toml). NOT WIRED.
├── prompts.py      questionary flow. Driven entirely by registry data.
├── staging.py      Destination conflicts, staging, atomic finalisation,
│                   cleanup. Engine-free; shared by runner.py and pipeline.py
│                   (ADR 0015).
├── runner.py       The ONLY module that touches Copier's Python API.
├── spec.py         Pure ProjectSpec wire-payload builder. No engine import.
├── compat.py       Engine range + protocol constants. No engine import;
│                   shared by cli.py's doctor and engine.py (ADR 0018).
├── engine.py       The ONLY module that touches the forge-template engine.
├── pipeline.py     Shared discover→build→validate→render→finalise pipeline.
│                   Reachable only via `new --engine-preview` (hidden,
│                   dev-only; ADR 0014, ADR 0015).
└── cli.py          Typer app: new, list, update, doctor.
```

Dependency direction is one-way: `cli` → `prompts`/`runner`/`registry`/
`staging` → `models`. Nothing lower imports anything higher. `engine.py` is
the only module whose *source* imports `forge_template`
(ADR 0013, [tests/test_engine_contract.py](tests/test_engine_contract.py));
`pipeline.py` depends on it but imports `forge_template` only under
`TYPE_CHECKING`. `cli.py` imports `pipeline`/`engine` lazily — inside
`--engine-preview`'s branch only, guarded by `try/except ImportError` — so
every other command stays unaffected by whether `forge-template` is
installed (ADR 0014). `staging.py` is engine-free and imported unconditionally
by both `runner.py` and `cli.py` — see the canonical
[filesystem generation contract](docs/filesystem-generation.md) (ADR 0015).

## Accepted target — engine available, CLI not integrated

[ADR 0010](docs/adr/0010-public-engine-integration-contract.md) accepts a
future one-way integration in which `create-forge` constructs ProjectSpec and
orchestrates the filesystem while a versioned `forge-template` package owns
ProjectSpec validation, component discovery, composition, rendering and
Copier. The living [integration contract](docs/integration-contract.md)
records the compatibility and trust rules for that transition.
Strict [ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
and [component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
are implemented by the
[stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
under [forge-template ADR 0029](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0029-stable-template-engine-api.md).
The engine's
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md)
is accepted under
[forge-template ADR 0030](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0030-generated-project-validation.md).
The accepted
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
and [forge-template ADR 0031](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0031-library-archetype-contract.md)
define the first production component, implemented on `forge-template/main`
and released at `0.3.0`. The accepted
[CLI Application archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
and [forge-template ADR 0034](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0034-select-cli-application-reference-archetype.md)
select the optionless engine-owned `cli` archetype and derive its command from
`ProjectSpec.project.repository_name`; FT-08.04 implemented it, and it ships
alongside `library` in the same `0.3.0` release.
This repository's development pair moved to `forge-template==0.3.0`
(CF-08.02, [ADR 0017](docs/adr/0017-cli-application-archetype-exposure.md)),
whose production catalogue is no longer empty, and then to a real released
range, `forge-template>=0.3.1,<0.4` ([#9](https://github.com/Sandsy09/create-forge/issues/9),
[ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md)),
declared as the optional `engine` extra (`create-forge[engine]`) rather than
a `[project.dependencies]` entry or a development-only pin. The boundary can
construct ProjectSpec, discover, validate, render, and finalise a project to
disk through the public facade; as of CF-07.01 this is reachable from a real
command via the hidden `new --engine-preview` flag (ADR 0014), though still
not from the default `new` path — ADR 0018 assigns a released range, it does
not perform the CLI cutover. CF-08.02 also adds a hidden `--archetype`
option and a discovery-driven interactive prompt, so `--engine-preview` now
selects for real between `library` and `cli` rather than passing a fixed id
through. The `forge-template>=0.3.1,<0.4` / protocol-1 pair is recorded by the
canonical [cross-repository engine contract tests](docs/engine-contract-tests.md).
`forge-template 0.3.2` is the current compatible release. `create-forge 0.2.1`
adds `uv>=0.12,<0.13` to the optional `engine` extra and creates `uv.lock` in
adjacent staging before the atomic rename (ADR 0021); render plans and the
public engine facade remain side-effect free.
CF-07.04 ([ADR 0015](docs/adr/0015-staged-filesystem-generation.md)) moved
the pin once, within the prior unreleased `0.2.0` contract, to adopt
generated-project validation; CF-08.02 ([ADR 0017](docs/adr/0017-cli-application-archetype-exposure.md))
moved it again, to the first tagged release; ADR 0018 replaced the pin
entirely with the released range above — `render_project` still calls the
public `validate_rendered_project` before returning. The canonical
[component discovery contract](docs/component-discovery.md) records the
protocol-first, no-fallback adapter semantics, and the canonical
[filesystem generation contract](docs/filesystem-generation.md) records how
`staging.py` stages and finalises a validated render, and how the Copier
path cleans up after a failure instead.
[ADR 0011](docs/adr/0011-engine-source-and-version-resolution.md) and the
living [engine resolution contract](docs/engine-resolution.md) define how
that engine is sourced, overridden for local development, diagnosed, and
rejected when incompatible. The installable runtime range is now implemented
(ADR 0018); the CLI cutover that makes it the default path is not.
[ADR 0013](docs/adr/0013-projectspec-construction-boundary.md) adds the first
code: `spec.py`/`engine.py` build and negotiate a ProjectSpec against
`forge-template`, now the optional `engine` extra rather than a
tag-pinned development dependency — see the canonical
[ProjectSpec construction contract](docs/project-spec-construction.md).
The canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
is a downstream-client input resolved before effective ProjectSpec
construction. CF-09.01 / [#53](https://github.com/Sandsy09/create-forge/issues/53)
([ADR 0022](docs/adr/0022-downstream-organisation-policy-hook.md)) delivered
that hook: `spec.SelectionRequest`/`SelectionProvenance` preserve whether each
selection kind was explicitly supplied, and
`pipeline.build_generation_request` accepts them as `selection`/`provenance`
keywords. The current CLI still consumes no policy itself and ships no
resolver — that is the decision, not an unfinished step; see the canonical
[downstream policy-consumption contract](docs/organisation-policy-consumption.md).
Forge-template Stage 09 is complete under the canonical
[safe extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
[organisation-policy fixture](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
[compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
and [no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md).
The last proof keeps Foundation/component source package-bound and private
catalogue overrides test-only. Do not duplicate engine content or infer a
plugin mechanism.
Forge-template [ADRs 0039–0042](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/README.md)
record those four decisions.
CF-09.02 / [#54](https://github.com/Sandsy09/create-forge/issues/54)
([ADR 0023](docs/adr/0023-downstream-client-reference.md)) added
[`examples/downstream_cli.py`](examples/downstream_cli.py): a second,
independent Blueprint-style CLI over the public `forge_template` facade,
carrying its own compatibility bounds and its own minimal organisation-policy
resolver. It imports no `create_forge` module — proven by an AST guard in
`tests/test_downstream_reference.py`, not merely stated — since it exists to
demonstrate that a downstream client needs nothing from this repository. See
the canonical [downstream client reference](docs/downstream-client-reference.md).
CF-09.03 / [#55](https://github.com/Sandsy09/create-forge/issues/55) completes
Stage 09 under
[ADR 0024](docs/adr/0024-reference-client-not-framework-dependency.md):
`create-forge` is one reference client rather than a framework dependency,
the supported engine has no reverse dependency, policy remains
selection-only, and generated projects depend on neither Forge package.
[ADR 0014](docs/adr/0014-lazy-engine-reachability.md) adds `pipeline.py` and
the hidden `new --engine-preview` flag that reaches this boundary from a real
command for the first time, via a lazily-imported module `cli.py` otherwise
never touches — the default `new` path remains unchanged. [ADR 0015](docs/adr/0015-staged-filesystem-generation.md)
completes that flag with real staging and finalisation via `staging.py`.
CF-07.06 ([ADR 0016](docs/adr/0016-end-to-end-reference-client-tests.md))
closes Stage 07 with real, CI-enforced coverage of the Copier path — the real
console script, its `_tasks`, and the generated project's own checks — see
the canonical [end-to-end tests contract](docs/end-to-end-tests.md).
CF-08.03 ([ADR 0019](docs/adr/0019-cli-archetype-parity-review.md)) reviewed
both archetypes for parity: the shared ProjectSpec/pipeline construction path
and engine-owned discovery hold generically, and the one archetype-specific
branch this repository had —
`pipeline._resolved_component_options`' legacy `library` option
derivation — is now gated by the selected archetype's own discovered
descriptor rather than a hardcoded id. That review also found, and left
unfixed, that `--engine-preview` still prompts from the Copier registry's
Library-shaped questions regardless of archetype — tracked by
[#91](https://github.com/Sandsy09/create-forge/issues/91), since fixing it
changes documented `--engine-preview` prompt-flow behaviour.
CF-08.04 ([ADR 0020](docs/adr/0020-engine-path-end-to-end-tests.md)) closed
CF-EPIC-08's last open child issue: the engine path now has the same real,
CI-enforced end-to-end coverage the Copier path already had — both
archetypes generated through `--engine-preview` against the real installed
engine, each project's own checks run, and a real released-install
compatibility boundary (an out-of-range engine, and no engine extra at all)
proven to write nothing. Forge-template's FT-08.05 review then corrected the
Foundation boundary in `0.3.2`; create-forge supplies the matching dynamic
lock finalisation under [ADR 0021](docs/adr/0021-client-finalises-engine-lockfiles.md).
The two-repository Stage 08 implementation is complete.

That target does not describe the current v0.1.x code. Until the coordinated
cutover lands, the architecture and invariants below remain authoritative. Do
not partially migrate ownership or weaken the bundled-source trust boundary in
advance of the roadmap issues that implement and test the complete contract.

## Invariants — do not break these

### 1. Registry prompt keys must exist in the template's copier.yml

Every `key` in a `[[templates.prompts]]` block must match a question in the
target template's `copier.yml`.

**This fails silently.** Copier ignores unknown keys passed via `data` — no
error, the answer vanishes, the template default applies. A typo produces a
scaffold that looks fine and is subtly wrong.

There is currently **no test guarding this**. Adding one is a priority task
(see backlog). It requires cloning the template repo, so mark it
`@pytest.mark.network`.

### 2. copier.yml is the source of truth for defaults

The CLI decides which questions get *asked*. It never redefines a question's
type, default, or validation. `runner.py` passes `defaults=True` so anything
unprompted falls back to the template. Adding a question to `copier.yml` must
never require a CLI change.

### 3. unsafe=True is load-bearing and dangerous

`runner.scaffold()` passes `unsafe=True` (the API form of `--trust`) because
templates declare `_tasks`. This executes code from whatever is cloned.

This is acceptable **only because template URLs are bundled** — they ship with
the reviewed release and cannot be altered at runtime. Do not add remote
registry fetching or config-based URL overrides without revisiting this. The
`--template-url` flag is the sanctioned escape hatch and prompts for
confirmation. See [ADR 0005](docs/adr/0005-execute-template-tasks.md) and
[ADR 0006](docs/adr/0006-bundled-registry-over-remote.md).

### 4. Copier's Python API is touched in exactly one place

`runner.py`. It is public but evolves faster than the CLI, hence the
`copier>=9.4,<10` pin. On a major bump, only that file should need attention.
See [ADR 0004](docs/adr/0004-copier-python-api-over-subprocess.md). `copier`
is today's *compatibility-line dependency* per
[ADR 0012](docs/adr/0012-engine-dependency-update-policy.md): Dependabot is
configured to never propose crossing that major on its own — see the
[engine update policy](docs/engine-updates.md). `engine.py` follows the same
one-module rule for `forge_template`, per
[ADR 0013](docs/adr/0013-projectspec-construction-boundary.md) — nothing
else in this package may import it. `cli.py` reaches it only through a
lazy, guarded import inside `--engine-preview`'s branch
([ADR 0014](docs/adr/0014-lazy-engine-reachability.md)) — `forge-template`
is the optional `engine` extra ([ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md)),
not installed by a plain `pip install create-forge`, so no module reachable
at `cli.py`'s own import time may depend on it, directly or through
`pipeline.py`. `compat.py` and `staging.py` are the exception that proves
the rule: both are imported unconditionally by `cli.py` (and `staging.py` by
`runner.py` too) precisely because they are engine-free by construction — no
`forge_template` import, not even under `TYPE_CHECKING`
([ADR 0015](docs/adr/0015-staged-filesystem-generation.md); ADR 0018).
`compat.py` holds the engine range and protocol constants both `cli.py`'s
`doctor` and `engine.py` need, so `doctor` can report them without ever
importing the engine itself.

Copier's Git transport can raise plumbum `ProcessExecutionError` directly
rather than a `CopierError`. `runner.py` owns that boundary too: translate it
to sanitized repository/ref/network/access guidance for both scaffold and
update, retain the original exception as the cause, and never display its raw
argv, stdout, or stderr because a template URL may contain credentials. Keep
this catch narrow; unrelated exceptions must not be hidden as user errors.

### 5. templates.toml must ship in the wheel

Editable installs read from source; wheels do not. A missing registry passes
every local test and breaks on a user's first `uvx` run. Verify with:

```bash
uv run poe check:wheel
```

Run this before any release.

## Conventions

- The canonical [CLI UX and prompting conventions](docs/cli-conventions.md)
  cover input precedence, prompt skipping, parity, validation ownership, and
  exit statuses. Treat them as a compatibility contract.
- The canonical [cross-repository contributor workflow](docs/cross-repository-workflow.md)
  defines how to validate sibling `create-forge` and `forge-template` changes
  before tagging or release.
- The canonical [engine resolution contract](docs/engine-resolution.md)
  defines how the template engine is sourced, overridden locally, diagnosed,
  and rejected when incompatible. Treat it as a compatibility contract.
- The canonical [engine update policy](docs/engine-updates.md) defines how a
  compatibility-line dependency update is adopted, how a breaking line is
  crossed, and what automated dependency tooling may never do on its own.
- The canonical [ProjectSpec construction contract](docs/project-spec-construction.md)
  defines the CLI-answer-to-ProjectSpec field mapping, derivation rules,
  protocol negotiation, and validation behaviour `spec.py`/`engine.py`
  implement.
- The canonical [component discovery contract](docs/component-discovery.md)
  defines protocol negotiation before catalogue access, descriptor ownership,
  and the no-fallback trust boundary implemented by `engine.py`.
- The canonical [cross-repository engine contract tests](docs/engine-contract-tests.md)
  define the supported package/protocol range, public-facade coverage,
  production-catalogue rendering boundary, and sibling-checkout command.
- The canonical [filesystem generation contract](docs/filesystem-generation.md)
  defines destination-conflict, staging, target-safety, finalisation, and
  cleanup rules implemented by `staging.py` and used by both `runner.py` and
  `pipeline.py`.
- The canonical [end-to-end tests contract](docs/end-to-end-tests.md) defines
  the fast/`network`/`e2e` test-tier split and what the real console script
  is proven to do, against a released template on the Copier path and the
  real installed engine on the engine path (CF-08.04, ADR 0020).
- The canonical
  [Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
  defines engine-owned Library semantics; this CLI owns only selection,
  ProjectSpec construction, and orchestration at the future cutover.
- The canonical
  [CLI Application archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
  defines the optionless `cli` component, exposed via `--engine-preview
  --archetype cli` since CF-08.02 ([ADR 0017](docs/adr/0017-cli-application-archetype-exposure.md)),
  and derives its console name from `ProjectSpec.project.repository_name`; do
  not duplicate those semantics in the registry or CLI models.
- The canonical [downstream policy-consumption contract](docs/organisation-policy-consumption.md)
  defines the `SelectionRequest`/`SelectionProvenance` seam CF-09.01
  ([ADR 0022](docs/adr/0022-downstream-organisation-policy-hook.md)) added to
  `pipeline.build_generation_request`, what may cross the engine boundary,
  and why `create-forge` deliberately ships no policy parser or resolver.
- The canonical [downstream client reference](docs/downstream-client-reference.md)
  defines `examples/downstream_cli.py` (CF-09.02,
  [ADR 0023](docs/adr/0023-downstream-client-reference.md)): a second,
  independent client demonstrating the public `forge_template` facade with no
  `create-forge` dependency, its own compatibility bounds, and its own
  minimal organisation-policy resolver.
- [ADR 0024](docs/adr/0024-reference-client-not-framework-dependency.md)
  closes the Stage 09 dependency boundary: shared engine logic stays in the
  supported `forge-template` facade, while clients remain independent.
- Python 3.11+ (`tomllib`, `StrEnum`)
- mypy strict; ruff with `ANN` and `D` enabled
- Conventional Commits (enforced by pre-commit once set up)
- `from __future__ import annotations` everywhere
- Pydantic models are `frozen=True, extra="forbid"`
- Errors shown to users go through `runner._explain()` or are phrased for a
  reader who has never used Copier

## Current state

Working: all six modules written and wired, registry validates, CLI structure
complete, `config.py` imported by `cli.py`, a test suite with a `copier.yml`
drift guard, a `pre-commit` gate mirrored in CI, the repo-hygiene files below
all present, `docs/adr/` records the decisions this file used to state without
their reasoning, `v0.1.0` is tagged and released — `uvx --from
git+https://github.com/Sandsy09/create-forge@v0.1.0 create-forge` verified end
to end from a clean environment — and `create-forge`/`create-forge[engine]`
are published to PyPI ([#9](https://github.com/Sandsy09/create-forge/issues/9),
[ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md)),
`forge-template`'s first assigned engine range.

Not yet done:
- MkDocs site ([#8](https://github.com/Sandsy09/create-forge/issues/8))

## Backlog, in order

See [docs/plan-v0.1.0.md](docs/plan-v0.1.0.md) for the phased roadmap covering
items 0-6 below (drift guard against `forge-template`'s `copier.yml`, test
suite, `config.py` wiring, repo hygiene, CI, ADRs, release) — written after a
`forge-template` session found a live bug here (`task_runner` still prompted
for after `forge-template` removed the question) and confirmed this CLI has
never been run end to end.

**0. Tag the template repo.** ✅ Done — `create-forge new` cannot work until
`forge-template` has a PEP440 tag; that is pushed.

**1. Test suite.** ✅ Done —
- `tests/test_registry.py` — bundled registry validates; ids unique; default
  exists and is not deprecated
- `tests/test_models.py` — validator behaviour (select without choices,
  deprecated without successor, duplicate keys)
- `tests/test_cli.py` — Typer's `CliRunner` against `list`, `doctor`,
  `new --dry-run`, `new --yes`, bad `--data` format
- `tests/test_drift.py` — invariant 1, marked `network`

Assert the *resolved Copier invocation* by monkeypatching `runner.scaffold`,
rather than actually scaffolding. Keep the real scaffold in one network test.

**2. Wire `config.py` into `cli.py`.** ✅ Done — `new` loads config and merges
`as_answers()` into `preset` **beneath** any `--data` values, so precedence runs
config < `--data` < prompt. `ValueError` from `load_config` is a user error.
Config state is surfaced in `doctor`.

**3. Repo hygiene.** ✅ Done — pre-commit config, `CONTRIBUTING.md`,
`SECURITY.md`, `LICENSE`, `CHANGELOG.md`, `.gitattributes`
(`* text=auto eol=lf` — the author develops on Windows), issue and PR
templates, CODEOWNERS.

**4. CI.** ✅ Done — lint (`pre-commit` + `mypy`), a test matrix over
3.11–3.14, a Windows smoke job, `scripts/check_wheel.py` (`poe check:wheel`),
and the `copier.yml` drift guard on push/PR and a Monday cron. `Dependabot`
covers `github-actions` and `uv`, not `.pre-commit-config.yaml`'s pinned revs.
Branch protection on `main` requires the `all-green` aggregate check.

**5. `docs/`.** ✅ Partially done — `docs/adr/` records the accepted decisions,
including the current Copier architecture, release version source, and the
future public-engine integration contract. `scripts/adr.py` (`poe check:adr`,
and `tests/test_adr.py` in the fast suite) keeps the set internally consistent.
MkDocs remains deferred —
[#8](https://github.com/Sandsy09/create-forge/issues/8).

**6. First release.** ✅ Done — [`release.yml`](.github/workflows/release.yml)
reads `pyproject.toml`'s `version` as the single source (ADR 0009, since
`forge-template`'s bump-choice model would let the tag and the package's own
`--version` drift apart). `v0.1.0` is tagged and released; `uvx --from
git+...@v0.1.0 create-forge new` verified end to end from a clean environment.
PyPI is a separate, deferred decision — [#9](https://github.com/Sandsy09/create-forge/issues/9).

## Deferred, with reasons

- **Remote registry override** — breaks the security property behind
  `unsafe=True`. Would need a signing or allowlist mechanism first.
- **GitHub repo creation and push** — deliberately out of scope. Would pull `gh`
  into the dependency tree and require the `workflow` OAuth scope, which is a
  confusing failure for users.
- **Interactive template browsing / search** — not useful with one template.

## Gotchas already hit

- `gh` pushes fail on `.github/workflows/**` without the `workflow` OAuth scope
  (`gh auth refresh -h github.com -s workflow`). Relevant if repo creation is
  ever added.
