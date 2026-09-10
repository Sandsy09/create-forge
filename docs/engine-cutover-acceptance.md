# Engine-Default Cutover Acceptance and Support

This is the living contributor contract for **how the engine-default cutover is
accepted and supported** — the concrete `create-forge` release that performs
it, the operating systems, Python versions and install modes it claims, the
cross-repository acceptance matrix and release gates that admit it, and the
rollback, support and deprecation windows that follow it.

It is the client-side companion of
[`docs/engine-default-cli.md`](engine-default-cli.md) (CF-16.01, the *selection
and source-resolution* rules) and
[`docs/engine-project-lifecycle.md`](engine-project-lifecycle.md) (CF-16.02,
the *`new` lifecycle and `update` dispatch* rules). Both deferred the same
short list here, by name: the concrete version numbers, the support and
deprecation windows, the cross-repository acceptance matrix, and the evidence
owners. It is the mirror of `forge-template`'s
[cutover-compatibility-and-acceptance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)
(FT-15.04 / forge-template ADR 0061) on the provider side.

It decides no runtime behaviour and ships nothing. It introduces no protocol
increment, no new component, no `copier.yml` change, and no package version
bump. It files no GitHub issue: every acceptance-matrix row and every gate maps
to an already-filed
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153) /
[FT-EPIC-18](https://github.com/Sandsy09/forge-template/issues/143) child, and
the roadmap dependency graph is
[`docs/roadmap-v3/github-issues/CROSS-REPO-DEPENDENCIES.md`](roadmap-v3/github-issues/CROSS-REPO-DEPENDENCIES.md),
already merged.

## Status

Accepted as a contract under
[ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md), the last
child of [CF-EPIC-16 / #152](https://github.com/Sandsy09/create-forge/issues/152).
Its design gate is the two accepted predecessor contracts (CF-16.01, CF-16.02)
and the four accepted `forge-template` Stage 15 contracts, all merged and
closed with `FT-EPIC-15`.

**This contract is not the cutover.** No `create-forge` release named here
exists yet. Until [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)
through [CF-18.07](https://github.com/Sandsy09/create-forge/issues/164)
implement, validate and publish it, the default `new` path stays direct-Copier
with a bundled registry, the engine stays the optional `engine` extra reachable
only through the hidden `new --engine-preview` flag, and
[`docs/cli-conventions.md`](cli-conventions.md) and
[`docs/integration-contract.md`](integration-contract.md) remain authoritative
for actual behaviour.

Its review obligations are **CF-ROADMAP-01-AC-06** (implementation, migration
E2E, legacy regression and release tasks are filed separately with an explicit
dependency graph — shared with
[CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) and
[CF-18.07](https://github.com/Sandsy09/create-forge/issues/164)) and
**CF-ROADMAP-01-EX-04** (no implementation or release in this decision issue —
owned solely here).

## The cutover release

**`create-forge 0.4.0` is the cutover release** — a single tagged minor bump on
the `0.x` line. In one release it:

- makes the `forge-template` engine the default `new` path (ADR 0040);
- moves `forge-template` from the optional `engine` extra into
  `[project.dependencies]` and `copier` into the optional `legacy` extra
  (ADR 0040);
- adopts the `forge-template>=0.5,<0.6` engine range — the mechanical bound
  move and lock refresh are
  [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)'s, not this
  contract's;
- removes `--engine-preview` and un-hides its five selection flags (ADR 0040);
- ships the engine `new` Git and hook lifecycle, the committed
  `.forge/generation.json` metadata file, and the engine-native
  `create-forge update` route (ADR 0041).

It is a **breaking** release: the default `new` behaviour and the resolved
dependency set both change. The `breaking-change` label on the release PR and a
migration section in the release notes carry that — not a `1.0.0`. Whether a
later release promotes the engine to `1.0.0`, and whether `template/` is ever
retired in favour of the catalogue, stay explicitly later decisions, exactly as
`forge-template` left `1.0.0` a later decision for itself.

`create-forge 0.4.0` pairs with the reviewed immutable `forge-template 0.5.0`
release. A pre-cutover patch release of `create-forge` (for unrelated fixes)
remains ordinary and is not governed here.

## Supported environment

Three axes. Each is a support *claim*: a combination outside it is not refused
where it happens to work, but it carries no proof row and no promise.

### Operating systems

| Platform | Claim | Proven by |
| --- | --- | --- |
| Linux (`ubuntu-latest`) | Supported | the full CI matrix and `e2e` job |
| Windows (`windows-latest`) | Supported | the `windows` fast-suite job, plus the acceptance-matrix Windows rows below for the engine `new` Git/hook lifecycle and the engine-native update |
| macOS | Expected to work; **not** a support claim | nothing — no CI runner in either repository |

The cutover newly makes the CLI run `git init`, `git commit` and
`pre-commit install` and perform a three-way merge over a user's working tree.
Those paths are OS-sensitive, so the acceptance matrix requires an explicit
Windows run of the engine `new` finalisation
([CF-18.03](https://github.com/Sandsy09/create-forge/issues/160)) and the
engine-native update
([CF-18.04](https://github.com/Sandsy09/create-forge/issues/161)) — coverage
today's Windows job does not give, because `e2e` runs on `ubuntu-latest` only.
A macOS runner is not added; if one is ever added, macOS moves to "Supported"
in the same change.

### Python

The supported window is the **latest four final CPython feature releases** —
today **3.11, 3.12, 3.13 and 3.14**. This is `create-forge`'s own copy of the
rule `forge-template`'s
[python-support.md](https://github.com/Sandsy09/forge-template/blob/main/docs/python-support.md)
applies to generated projects but explicitly disclaims for the CLI itself.

| Control | Rule |
| --- | --- |
| `requires-python` floor | the oldest release in the active window (today `>=3.11`), no upper cap |
| Classifiers | enumerate the active window |
| CI `test` matrix | the active window |
| `floor` job | the oldest active release |

Admitting a new CPython release, and retiring the outgoing oldest one, follow
the same evidence gate `forge-template` uses (locked dependencies resolve,
schema and rendering accept it, every scaffold combination passes, a boundary
scenario exercises it, generated CI passes) and the deprecation notice period
below. **The floor does not move at the cutover** — nothing in the engine path
requires it, and `forge-template`'s own floor is `>=3.11`.

### Install modes

Four modes are contractual. Each has an acceptance-matrix row proving a fresh
install resolves the engine and generates.

| Mode | Command | Notes |
| --- | --- | --- |
| Ephemeral | `uvx create-forge` | may reuse a cache; the primary documented path |
| Persistent | `uv tool install create-forge` | `uv tool upgrade` / `uninstall` manage it |
| Environment | `pip install create-forge` | into an active virtual environment |
| Legacy route | `create-forge[legacy]` through any of the above (e.g. `pip install 'create-forge[legacy]'`) | adds `copier` back for `--legacy` `new` and `update` |

`pip install create-forge` becomes a documented, tested mode because ADR 0040's
accepted diagnostics already print `pip install 'create-forge[legacy]'` as a
remedy — the string must name a supported path. `pipx` is not a contractual
mode.

## The cross-repository acceptance matrix

Every row names one non-interactive check with a binary outcome, one evidence
command, one owning issue, and the Stage 18 child it is **first required at** —
"required" as FT-10.04 fixed it: the command exists and can be run the moment
its stage arrives, not once it passes. Every Stage 18 client child owns at
least one row; every row names a filed issue.
[`tests/test_cutover_acceptance_contract.py`](../tests/test_cutover_acceptance_contract.py)
checks both directions.

Evidence-command paths are targets the implementing issue meets; a suite that
does not exist yet is named descriptively (`tests/test_e2e_installed_cutover.py`
is the installed-console suite
[CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) adds, the
analogue of `tests/test_e2e_installed_rollout.py`).

### Default engine generation

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| A plain `uvx create-forge` / `pip install create-forge` resolves `forge-template>=0.5,<0.6`; `create-forge new "<name>"` with no route flag constructs a ProjectSpec, discovers the catalogue, validates, renders and finalises through the public facade, with no production-catalogue branch | `uv run pytest tests/test_e2e_engine_generation.py` | CF-18.01 | CF-18.01 |
| `list` and `doctor` run against the discovered catalogue and negotiate the real engine while staying offline; `doctor --json` reports package version and both protocol tuples | `uv run pytest tests/test_cli.py -k "doctor or list"` | CF-18.01 | CF-18.01 |
| Data still flows `create-forge → ProjectSpec → forge-template render → create-forge finalisation`; no component semantics or resources are copied downstream (**CF-ROADMAP-01-AC-02**) | `uv run pytest tests/test_engine_contract.py` (AST guard, widened) | CF-18.01 | CF-18.01 |
| Each of the four install modes resolves the engine and generates from an isolated environment | `uv run pytest tests/test_e2e_installed_cutover.py -k install_modes` | CF-18.06 | CF-18.06 |

### Engine-source overrides

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| `--engine-source` / `--engine-ref` provision an isolated environment, pass the same public compatibility check before rendering, and do not contaminate an ordinary install | `uv run pytest tests/test_engine_source.py` | CF-18.02 | CF-18.02 |
| Source credential / query / fragment restrictions and literal-text warnings are preserved; the warning still shows under `--yes`; unsafe inputs fail before prompts or subprocess effects | `uv run pytest tests/test_engine_source.py -k "unsafe or credential"` | CF-18.02 | CF-18.02 |
| An `--engine-source` render writes **no** `.forge/generation.json` and the project is reported not update-eligible at generation time | `uv run pytest tests/test_engine_source.py -k metadata` | CF-18.02 | CF-18.02 |

### Engine generation finalisation, Git and hooks

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| Validated render and dynamic `uv.lock` are applied through staging and one atomic rename; then, at the final path, `git init` + `git add -A` + one initial commit; `pre-commit install --install-hooks` only when `.pre-commit-config.yaml` was rendered | `uv run pytest tests/test_e2e_engine_generation.py -k "finalise or lifecycle"` | CF-18.03 | CF-18.03 |
| The same finalisation on `windows-latest` — path separators, line endings, hook shims | `uv run pytest tests/test_e2e_engine_generation.py -k lifecycle` on `windows-latest` | CF-18.03 | CF-18.03 |
| A `git init` / commit / `pre-commit install` failure after a good render keeps the project, prints the one manual command, and exits `0`; a render / lock / rename failure cleans up and exits `1`, deleting no pre-existing user content (**CF-ROADMAP-01-AC-03**) | `uv run pytest tests/test_e2e_engine_generation.py -k "failure or cleanup"` | CF-18.03 | CF-18.03 |

### Engine-native update

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| `create-forge update` routes to the engine-native Git-backed three-way merge on `.forge/generation.json`, to `copier update` on `.copier-answers.yml` only, and `update --legacy` forces Copier; neither file is exit `1` naming both routes | `uv run pytest tests/test_update_routing.py` | CF-18.04 | CF-18.04 |
| A clean-tree update applies rename records first, merges old / new / working tree per target with inline conflict markers left staged, deletes a `removed` target only if pristine, and never touches a `skip-if-exists` target; file add / delete / rename, no-op and repeated updates all classify correctly | `uv run pytest tests/test_update_engine.py` | CF-18.04 | CF-18.04 |
| `update --dry-run` writes nothing and prints the per-target classification list; malformed metadata, `Ctrl-C` and a failed merge leave a recoverable project and print (never run) `git restore . && git clean -fd`; `.forge/generation.json` is rewritten last (**CF-ROADMAP-01-AC-03**) | `uv run pytest tests/test_update_engine.py -k "dry_run or recover"` | CF-18.04 | CF-18.04 |
| An unavailable recorded release fails closed with the four report facts; the opt-in `--degraded` two-way update records `reproduction.mode = "degraded"` | `uv run pytest tests/test_update_engine.py -k degraded` | CF-18.04 | CF-18.04 |
| The engine-native update on `windows-latest` | `uv run pytest tests/test_update_engine.py` on `windows-latest` | CF-18.04 | CF-18.04 |

### Legacy Copier route

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| `create-forge[legacy]` installs `copier`; `new --legacy` and `update` against a recorded `.copier-answers.yml` project run real tagged Copier generation and update, preserving local edits and reaching HEAD; `--legacy` without the extra exits `3` naming the remedy | `uv run pytest tests/test_e2e_installed_cutover.py -k legacy` | CF-18.05 | CF-18.05 |
| `--template` / `--template-url` / `--ref` and `_src_path` source validation are retained under `--legacy`; custom sources, user edits and `--dry-run` all work | `uv run pytest tests/test_cli.py -k legacy` | CF-18.05 | CF-18.05 |
| A `create-forge` pinned to `forge-template>=0.4.1,<0.5` still resolves, installs and generates after `0.5.0` publishes | `create-forge` regression suite against the `0.4.1` pin (see `forge-template` matrix, FT-18.01 row) | FT-18.01 | FT-18.01 |

### Preview-project transition

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| A project scaffolded through the removed `--engine-preview` flag (neither answers file) is rejected by `update` with exit `1` and actionable guidance; no answers are fabricated or corrupted (**CF-ROADMAP-01-AC-05**) | `uv run pytest tests/test_update_routing.py -k preview` | CF-18.05 | CF-18.05 |
| Existing `.copier-answers.yml` projects keep the documented update route and the rollback plan does not corrupt their stored answers (**CF-ROADMAP-01-AC-05**) | `uv run pytest tests/test_update_network.py` | CF-18.05 | CF-18.05 |

### Failure paths

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| A missing or incompatible engine, an invalid selection, and a render / finalise failure each fail with a stable status (`1`, `3`, or `130`) and never silently fall back to Copier or the bundled registry (**CF-ROADMAP-01-AC-04**) | `uv run pytest tests/test_e2e_installed_cutover.py -k "incompatible or invalid or failure"` | CF-18.06 | CF-18.06 |
| An out-of-range engine and no-engine install write nothing and are visible in `doctor` | `uv run pytest tests/test_e2e_installed_cutover.py -k boundary` | CF-18.06 | CF-18.06 |
| Diagnostics never echo raw argv, stdout, stderr, source or ref; source secrets are stripped | `uv run pytest tests/test_cli.py tests/test_runner.py -k "credential or secret"` | CF-18.06 | CF-18.06 |

### Cross-repository integrated validation

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| The immutable released `forge-template 0.5.0` paired with the `create-forge 0.4.0` candidate passes the full cross-repository acceptance matrix | `create-forge` end-to-end suite against the published `0.5.0` release (see `forge-template` matrix, FT-18.01 row) | FT-18.01 | FT-18.01 |
| The installed candidate console covers default generation, overrides, engine updates, legacy updates and the preview-project transition across the supported OS / Python / install-mode matrix | `uv run poe test:e2e` (`tests/test_e2e_installed_cutover.py`) | CF-18.06 | CF-18.06 |
| Migration, legacy-support, rollback and user-guide recipes are updated and exercised; diagnostic fields and statuses stay stable per the compatibility contract | `uv run poe docs:build` plus the recipe checks in `tests/test_e2e_installed_cutover.py` | CF-18.06 | CF-18.06 |

### Publication

| Check | Evidence command | Owner | First required at |
| --- | --- | --- | --- |
| Both integrated evidence sets and every protected check — including working engine-native updates and the supported legacy route — pass before publication | `all-green` on `main` plus the two integrated suites | CF-18.07 | CF-18.07 |
| `0.4.0` is published only through CONTRIBUTING's protected `release.yml` with `dry_run: true` inspected first; the built wheel ships `templates.toml` | `release.yml` dry run then dispatch; `uv run poe check:wheel` | CF-18.07 | CF-18.07 |
| The tag, GitHub Release and PyPI wheel/sdist name one commit SHA; the published CLI verifies against the reviewed `forge-template 0.5.0` artefacts; documentation deploys; install / update / support / rollback instructions are verified | published-artefact audit; live-site check | CF-18.07 | CF-18.07 |

## Release sequencing and gates

The one-way dependency `create-forge → forge-template → generated project`
holds, and the provider merges and releases before the client adopts the line.
`forge-template`'s
[cutover-compatibility-and-acceptance.md § Cross-repository release gates](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)
is the shared gate table; `create-forge`'s
[integration contract § Release coordination](integration-contract.md) is
authoritative for the client-side mechanics. This contract instantiates them
for the cutover:

1. **`create-forge` Stage 16 contracts accepted.** CF-16.01, CF-16.02 and this
   contract merged on protected `main`; `CF-EPIC-16` closed. `FT-EPIC-17` is
   blocked on this exit.
2. **`forge-template` Stage 17 implementation.** FT-17.01–FT-17.05 merged;
   every provider Engine / Generated-project / Independence / Regression row
   passed on protected `main`.
3. **Reviewed `forge-template 0.5.0`.** Published through the protected release
   workflow; tag, GitHub Release and PyPI artefacts name one commit SHA; the
   `0.4.x` line stays installable. [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)
   is blocked on this.
4. **`create-forge >=0.5,<0.6` adoption.** Engine bound widened, lock
   refreshed; `0.3` and out-of-range engines fail before generation; plain
   installs unaffected.
5. **Integrated cutover validation.** The released provider paired with the
   candidate client passes the full matrix together
   ([FT-18.01](https://github.com/Sandsy09/forge-template/issues/156) +
   [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163)). A provider
   defect requires a corrected reviewed release and renewed client adoption
   evidence — never a moving branch.
6. **`create-forge 0.4.0` publication.** Only after gate 5 and working
   engine-native **and** legacy updates
   ([CF-18.07](https://github.com/Sandsy09/create-forge/issues/164),
   **CF-ROADMAP-01-AC-07**).

Merging is not releasing. A merge to `main` leaves it untagged and invisible to
a version-pinned engine client until `release.yml` runs.

## Rollback and support windows

**Release rollback.** A published `create-forge` release is **immutable** — a
defect is never fixed by mutating an artefact. It is corrected forward as
`0.4.1` (or a new line), and the defective version is **yanked** from PyPI so
no new install resolves it. This matches
[CONTRIBUTING.md § Releasing](../CONTRIBUTING.md#releasing) and `release.yml`,
which already reject an existing or non-increasing tag.

**The `0.3.x` support window.** `create-forge 0.3.x` — the last direct-Copier
default line — stays installable and supported for **at least 90 days and at
least one further tagged `create-forge` release** past the cutover.
`create-forge 0.3.2` resolves `forge-template>=0.4.1,<0.5`, so a user who hits
a `0.4.0` defect can pin `create-forge==0.3.2` and keep generating while a fix
ships. The acceptance matrix carries the row proving that pin-back path still
resolves, installs and generates after `0.4.0` publishes. This is a new
client-side commitment modelled on `forge-template`'s `0.4.x` window, not an
inheritance.

**User-project rollback** — restoring a working tree and its stored
`.forge/generation.json` after a bad update — is the clean-tree precondition
and the printed `git restore . && git clean -fd` recovery ADR 0041 already
fixed, implemented by
[CF-18.04](https://github.com/Sandsy09/create-forge/issues/161) /
[CF-18.05](https://github.com/Sandsy09/create-forge/issues/162). It is not a
release-process concern.

## Deprecation

**The window.** Any visible flag or behaviour this cutover retires *later*
carries a deprecation warning naming its replacement for **at least 90 days and
at least one further tagged `create-forge` release**, with layered notice
through this contract's support statements, a tracking issue and pull request,
the CLI's own warning text, and the release notes. This is the same shape
`forge-template`'s
[compatibility-policy.md](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md)
commits to for every provider axis, so the two repositories state one number.
`create-forge` cites that policy rather than restating it; changing the number
needs an ADR superseding `forge-template` ADR 0041.

**`--engine-preview` is removed in `0.4.0` with no window.** It is hidden,
absent from `--help` and documented development-only, so it has no
compatibility promise to honour (ADR 0040 decision 34). The release that makes
it meaningless removes it — an unknown option, exit `2`.

**The direct-Copier route is not deprecated and starts no clock.** `--legacy`,
`--template`, `--template-url`, `--ref`, the bundled registry and
`create-forge update` against a `.copier-answers.yml` project all stay
supported (ADR 0040 decision 33), because `forge-template` guarantees
`template/`, `copier.yml` and `copier update` remain live. Retiring the
client's entry point to them is not on this roadmap.

**No calendar dates.** Every window is expressed relative to the cutover
publication — days elapsed and releases tagged — because `create-forge`
releases are irregular and manually triggered, the same reason `forge-template`
gives. The policy is fixed; no date is invented.

## What this contract does not decide

- The **implementation** of every acceptance-matrix row — the engine range
  adoption, the isolated-environment override, the `new` finalisation, the
  engine-native update engine, the legacy and preview-project transition —
  [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) through
  [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162).
- The **execution** of the matrix and the recording of commands, platforms,
  versions and artefact identities —
  [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) and the
  provider-owned integrated rows,
  [FT-18.01](https://github.com/Sandsy09/forge-template/issues/156).
- The **publication** of `create-forge 0.4.0`, its release notes and its
  rollback guidance —
  [CF-18.07](https://github.com/Sandsy09/create-forge/issues/164).
- `forge-template`'s provider internals — the manifest-`3` schema, the
  `get_engine_info()` metadata hand-off, the reproducible-render implementation,
  the two reserved `EngineErrorCode` values — FT-17.01 / FT-17.04.
- Whether a future release promotes the engine to `1.0.0`, and retiring
  `template/` in favour of the catalogue.
- The Streamlit archetype and its client adoption —
  [roadmap-v4](roadmap-v4/README.md), which enters after this contract is
  accepted.
- Any `forge-template` change. Provider manifests, composition, generated
  content and in-memory validation stay in `forge-template`
  (**CF-ROADMAP-01-EX-01**); this contract adds no archetype
  (**CF-ROADMAP-01-EX-02**) and no remote registry or plugin mechanism
  (**CF-ROADMAP-01-EX-03**). It implements and releases nothing
  (**CF-ROADMAP-01-EX-04**).

## Executable examples

Until the cutover ships, the contract is guarded rather than characterised:

- [`tests/test_cutover_acceptance_contract.py`](../tests/test_cutover_acceptance_contract.py)
  derives what it can from the live pre-cutover repository — `create-forge` is
  still on the `0.3` line, `requires-python` is still `>=3.11`, the classifiers
  are still 3.11–3.14, there is no `legacy` extra — and checks the matrix
  itself: every row names an issue in
  [`docs/roadmap-v3/github-issues/filing-manifest.json`](roadmap-v3/github-issues/filing-manifest.json)
  (the mechanism `forge-template`'s `tests/test_cutover_gates.py` uses), and
  every Stage 18 client child owns at least one row. It carries tripwires that
  fail deliberately when
  [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) /
  [CF-18.06](https://github.com/Sandsy09/create-forge/issues/163) /
  [CF-18.07](https://github.com/Sandsy09/create-forge/issues/164) land, so the
  implementation cannot ship without bringing this document back into step. It
  also asserts
  [ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md) names
  its `CF-ROADMAP-01-AC-06` and `CF-ROADMAP-01-EX-04` obligations literally.
- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s
  link-audit guard keeps this document reachable from `CLAUDE.md`,
  `CONTRIBUTING.md` and [`docs/cli-conventions.md`](cli-conventions.md).

When the cutover implements a rule above, move it from this contract's
"decided" voice into the "in force" voice of
[`docs/cli-conventions.md`](cli-conventions.md) or
[`docs/integration-contract.md`](integration-contract.md), and add its
characterization test, in the same pull request.
