# CLAUDE.md — create-forge

Guidance for Claude Code working in this repository.

## What this is

`create-forge` is a CLI that scaffolds Python projects, analogous to
`pnpm create-payload-app`. It is a **thin wrapper**: a `forge-template` engine
(or, via `--legacy`, Copier) does the rendering, this tool owns the prompt
experience and orchestration.

Distributed via `uvx create-forge` and published to PyPI as `create-forge`
(`pip install create-forge`). The `forge-template` engine is the default `new`
architecture and a required dependency; `pip install 'create-forge[legacy]'`
adds `copier` back for the explicit `--legacy` route. Public, MIT, intended for
open-source use.

## Repository relationship

Two repositories, deliberately separate:

| Repo | Role |
| --- | --- |
| `https://github.com/Sandsy09/create-forge` | This repo. The CLI. |
| `https://github.com/Sandsy09/forge-template` | The templates it scaffolds from. |

They are split because Copier resolves template versions from PEP440 git tags
in the template repo. A shared repo would make `v1.3.0` ambiguous between the
two codebases. **Do not merge them.** See
[ADR 0003](docs/adr/0003-two-repo-split.md).

## Architecture

```
src/create_forge/
├── models.py         Pydantic v2 models for the registry. No I/O.
├── templates.toml    Bundled registry data. Package data, ships in the wheel.
├── registry.py       Loads + validates templates.toml. Cached.
├── config.py         User config (~/.config/create-forge/config.toml).
├── prompts.py        questionary flow. Driven entirely by registry data.
├── staging.py        Destination conflicts, staging, atomic finalisation,
│                     cleanup. Engine-free; shared by every generation route.
├── sources.py        Untrusted-source validation/display (--template-url,
│                     --engine-source). Engine-free.
├── descriptors.py     DescriptorView/OptionView/RelationView protocols +
│                     their JSON mirror models. Engine-free.
├── runner.py         The ONLY module that touches Copier's Python API.
├── spec.py           Pure ProjectSpec wire-payload builder. No engine import.
├── compat.py         Engine range/protocol constants + the shared
│                     compatibility check. No engine import; shared by
│                     cli.py's doctor, engine.py, and engine_source.py.
├── engine.py         Touches the installed forge-template engine, in
│                     process.
├── engine_source.py  --engine-source/--engine-ref: provisions an isolated
│                     engine and runs _engine_worker.py inside it. No engine
│                     import in the parent process.
├── _engine_worker.py Runs *inside* a provisioned engine only, as a script,
│                     never imported. Touches forge-template out of process.
├── pipeline.py       Shared discover→build→validate→render→finalise pipeline,
│                     plus `Catalogue` (one discovery, grouped by kind).
└── cli.py            Typer app: new, list, update, doctor.
```

Dependency direction is one-way: `cli` → `prompts`/`runner`/`registry`/
`staging` → `models`. Nothing lower imports anything higher. `engine.py` (in
process) and `_engine_worker.py` (out of process, run inside a provisioned
`--engine-source` environment that never has `create-forge` installed) are
the only two modules whose *source* imports `forge_template`
(ADR 0013 as amended by ADR 0044,
[tests/test_engine_contract.py](tests/test_engine_contract.py)); `pipeline.py`
depends on `engine.py` but imports `forge_template` only under
`TYPE_CHECKING`. `copier` is behind the optional `legacy` extra, so
`runner.py` is imported lazily by `cli.py`'s `--legacy` route and by `update`.
`compat.py`, `staging.py`, `sources.py`, `descriptors.py`, and
`engine_source.py` are engine-free by construction (no `forge_template`
import, not even under `TYPE_CHECKING`) and are imported unconditionally —
see the canonical [filesystem generation contract](docs/filesystem-generation.md)
(ADR 0015) and [engine resolution contract](docs/engine-resolution.md)
(ADR 0044).

## Change process

Run this loop for every issue or change:

1. **Plan first.** Read the issue and whichever canonical contracts in
   [docs/README.md](docs/README.md) it touches. Surface every open
   implementation question before writing the plan — no assumption left
   unstated.
2. **Decide whether it is a decision.** A new or changed architecture
   boundary, dependency range, or CLI surface needs an ADR in `docs/adr/`
   (Nygard format: `## Status`/`## Context`/`## Decision`/`## Consequences`).
   Records are immutable — supersede, never edit. `uv run poe check:adr`
   enforces filenames, contiguous numbering, the index entry, and the four
   headings.
3. **Move the contracts with the change.** If a canonical `docs/*.md`
   contract describes the behaviour you're changing, update it in the same
   PR. Several have link-audit or byte-exact guard tests — see
   [docs/README.md](docs/README.md).
4. **Implement**, matching the surrounding code's idiom and comment density.
5. **Verify.** `uv run poe check` always. Add `pytest -m network` when
   `templates.toml` changes, `uv run poe test:e2e` at the engine boundary, and
   `uv run poe check:wheel` before any release.
6. **Ship.** Branch, Conventional Commit, open a PR, wait for
   `All checks passed`, squash-merge, delete the branch, fast-forward local
   `main`.

## Invariants — do not break these

### 1. Registry prompt keys must exist in the template's copier.yml

Every `key` in a `[[templates.prompts]]` block must match a question in the
target template's `copier.yml`.

**This fails silently.** Copier ignores unknown keys passed via `data` — no
error, the answer vanishes, the template default applies. A typo produces a
scaffold that looks fine and is subtly wrong.

`tests/test_drift.py` guards this against the latest released template and an
explicit sibling checkout. It is marked `network` because the release path
clones the template repository.

### 2. copier.yml is the source of truth for defaults

The CLI decides which questions get *asked*. It never redefines a question's
type, default, or validation. `runner.py` passes `defaults=True` so anything
unprompted falls back to the template. Adding a question to `copier.yml` must
never require a CLI change.

### 3. unsafe=True is load-bearing and dangerous

`runner.scaffold()` passes `unsafe=True` (the API form of `--trust`) because
templates declare `_tasks`. This executes code from whatever is cloned. The
default is acceptable because template URLs are bundled — they ship with the
reviewed release and cannot be altered at runtime. Do not add remote registry
fetching or config-based URL overrides without revisiting this. `--template-url`
is the sanctioned explicit escape hatch: it validates the source, warns about
code execution, and prompts for confirmation unless `--yes` was supplied. See
[ADR 0005](docs/adr/0005-execute-template-tasks.md),
[ADR 0006](docs/adr/0006-bundled-registry-over-remote.md), and
[ADR 0036](docs/adr/0036-template-source-credentials.md).

### 4. Copier's and the engine's Python APIs are each touched in exactly one place (two, for the engine)

`runner.py` for Copier (`copier>=9.16,<10`); `engine.py` for the *installed*
`forge_template`, in process. ADR 0044 adds the one deliberate second seam:
`_engine_worker.py` also imports `forge_template`, but only ever runs inside a
`--engine-source`-provisioned environment as a subprocess script — never
imported by the parent, and never in the same interpreter as `engine.py`'s
own import, so the two cannot collide. Nothing else in this package may
import either Copier or `forge_template`. On a major bump, only `runner.py`
or `engine.py` (plus, for a wire-protocol change, `_engine_worker.py`) should
need attention. `compat.py` holds the shared engine range, protocol
constants, and the compatibility-check functions themselves, so `doctor` can
report them without importing the engine, and `engine.py`/`engine_source.py`
apply the identical check to the installed and a provisioned engine
respectively. Copier's Git transport can raise plumbum
`ProcessExecutionError` directly rather than a `CopierError` — `runner.py`
translates it to sanitized repository/ref/network/access guidance, retains
the original as the cause, and never displays raw argv, stdout, or stderr (a
template URL may carry credentials); `engine_source.py` applies the same
never-echo-verbatim rule to `uv`'s own process failures. Keep both catches
narrow. See [ADR 0004](docs/adr/0004-copier-python-api-over-subprocess.md),
[ADR 0012](docs/adr/0012-engine-dependency-update-policy.md),
[ADR 0013](docs/adr/0013-projectspec-construction-boundary.md),
[ADR 0044](docs/adr/0044-out-of-process-engine-source-overrides.md), and the
[engine update policy](docs/engine-updates.md).

### 5. templates.toml must ship in the wheel

Editable installs read from source; wheels do not. A missing registry passes
every local test and breaks on a user's first `uvx` run. Verify with:

```bash
uv run poe check:wheel
```

Run this before any release.

### 6. External Actions are pinned to reviewed commits

Every external `uses:` in `.github/workflows/` is a full 40-character commit
SHA with an adjacent `# vX.Y.Z` comment — not a branch or tag, which can be
repointed after review. Workflow-level `permissions:` is read-only
(`contents: read`); `write` and `id-token` scopes exist only on the individual
`release`/`publish`/`deploy` jobs that need them. `docker://` and
repository-local (`./…`) references are the only exceptions.
`scripts/check_workflows.py` (`uv run poe check:workflows`, and
`tests/test_workflows.py` in the fast suite) enforces both. See
[ADR 0037](docs/adr/0037-immutable-workflow-actions.md) and the canonical
[workflow security contract](docs/workflow-security.md).

## Conventions

- Canonical contracts governing CLI behaviour, the engine boundary, and
  release/security process are indexed in [docs/README.md](docs/README.md) —
  treat them as compatibility contracts, not background reading.
- Python 3.11+ (`tomllib`, `StrEnum`)
- mypy strict; ruff with `ANN` and `D` enabled
- Conventional Commits (enforced by pre-commit once set up)
- `from __future__ import annotations` everywhere
- Pydantic models are `frozen=True, extra="forbid"`
- Errors shown to users go through `runner._explain()` or are phrased for a
  reader who has never used Copier

## Out of scope, with reasons

- **Remote registry override** — breaks the security property behind
  `unsafe=True`. Would need a signing or allowlist mechanism first.
- **GitHub repo creation and push** — deliberately out of scope. Would pull
  `gh` into the dependency tree and require the `workflow` OAuth scope, which
  is a confusing failure for users.
- **Interactive template browsing / search** — not useful with one template.

## Current state

`create-forge 0.4.0` is the latest **tagged and published** release — the
Engine-Default Cutover (CF-EPIC-18, ADR 0049). The `forge-template` engine is
the default, required `new` path (`forge-template>=0.5,<0.6`); `copier` moved
to the optional `legacy` extra. It ships the isolated `--engine-source`/
`--engine-ref` override (CF-18.02, ADR 0044), the engine `new` Git/hook
lifecycle plus the committed `.forge/generation.json` metadata file
(CF-18.03, ADR 0045), and engine-native `update` dispatch — a Git-backed
three-way merge via `git merge-file`, a genuine per-target `--dry-run`, and
an opt-in `--degraded` fallback (CF-18.04, ADR 0046). `--engine-preview` no
longer exists. `create-forge 0.3.x` — the last direct-Copier default line —
stays installable and supported for at least 90 days and at least one
further tagged release past `0.4.0` (`uv tool install "create-forge==0.3.2"`).
See [docs/roadmap-v3/](docs/roadmap-v3/) and
[docs/engine-cutover-acceptance.md](docs/engine-cutover-acceptance.md) for the
cutover contract, [docs/release-0-4-0-validation.md](docs/release-0-4-0-validation.md)
for the published-artefact evidence, and [docs/README.md](docs/README.md) for
everything else. The next roadmap is Streamlit
([docs/roadmap-v4/](docs/roadmap-v4/)).

## Gotchas already hit

- `gh` pushes fail on `.github/workflows/**` without the `workflow` OAuth
  scope (`gh auth refresh -h github.com -s workflow`). Relevant if repo
  creation is ever added.
- This repo's Actions policy is **Allow select actions** (Settings → Actions →
  General). A `uses:` pattern not in `patterns_allowed` fails the whole run at
  startup with no log — `startup_failure`, 0s. Entries use `owner/repo@*` so
  SHA pins match; a new third-party action needs an allowlist entry (`gh api
  --method PUT
  repos/Sandsy09/create-forge/actions/permissions/selected-actions`) added
  with it. See [ADR 0037](docs/adr/0037-immutable-workflow-actions.md).
