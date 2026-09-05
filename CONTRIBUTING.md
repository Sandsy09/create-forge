# Contributing

This describes the human workflow — how to set up, validate, and release a
change. For the rules that keep `create-forge` correct — how the registry
relates to `forge-template`'s `copier.yml`, why `unsafe=True` is load-bearing,
and so on — see [CLAUDE.md](CLAUDE.md); this file won't restate them.

## Setup

```bash
uv sync --all-groups --all-extras
uv run pre-commit install --install-hooks
```

`--all-extras` resolves `forge-template>=0.4.1,<0.5` and `uv>=0.12,<0.13`
from PyPI as the optional `engine` extra
([#9](https://github.com/Sandsy09/create-forge/issues/9),
[ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md);
range moved to the 0.4 line by
[ADR 0026](docs/adr/0026-adopt-the-0-4-engine-compatibility-line.md), with the
reviewed `0.4.1` release adopted by
[ADR 0031](docs/adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md)) --
plain `uv sync` (or `pip install create-forge`) never resolves it. That
optionality is what lets `src/create_forge/engine.py` — see
[ADR 0013](docs/adr/0013-projectspec-construction-boundary.md) — stay out of
every `uvx create-forge` user's install. Omit `--all-extras` to work on
anything that doesn't touch `--engine-preview`, `engine.py`, or `pipeline.py`.

## Before opening a pull request

```bash
uv run poe check
```

Runs `ruff format --check`, `ruff check`, `mypy`, and the fast test suite —
`pytest -m 'not network and not e2e'`.

The network-marked tests are separate:

```bash
uv run pytest -m network
```

This hits GitHub and includes two things: `tests/test_drift.py`, which clones
`forge-template` and checks every prompt key in `templates.toml` still matches
a question in its `copier.yml`; and `tests/test_update_network.py`, a real
end-to-end `create-forge update` against `forge-template`'s actual tags.

The drift check exists because a mismatch fails *silently* — Copier drops an
unknown `data` key with no error, the answer vanishes, and the template's own
default applies instead. A typo here produces a scaffold that looks fine and
is subtly wrong, which is exactly the failure mode this test is for. Run it
whenever `templates.toml` changes, or whenever `forge-template` cuts a new tag.

## End-to-end tests

A third tier, separate from both the fast suite and `network`:

```bash
uv run poe test:e2e
```

This runs the real `create-forge` console script through the Copier and engine
paths, then each generated project's own checks. CF-14.02 also builds the
create-forge `0.3.0` candidate wheel, installs it with the published
`forge-template 0.4.1` engine, and validates both Data Science compositions
through that isolated console script across the provider handoff's Python
matrix. It is dramatically slower than `network`, so it carries its own
`e2e` marker and CI job. The Copier and released-install negative tests skip
when GitHub is unreachable; the installed Data Science suite treats resolving
the reviewed PyPI engine as part of its proof. See the canonical
[end-to-end tests contract](docs/end-to-end-tests.md),
[installed Data Science validation](docs/installed-data-science-validation.md),
[ADR 0016](docs/adr/0016-end-to-end-reference-client-tests.md), and
[ADR 0032](docs/adr/0032-validate-installed-data-science-generation.md).

Before any release, also run:

```bash
uv run poe check:wheel
```

Editable installs read `templates.toml` from source; a built wheel does not
unless Hatchling's package-data rules are still correct. A missing registry
passes every test above and only breaks on a user's first `uvx` run — this is
the one check that catches it ahead of time.

## Cross-repository changes

Changes that coordinate this CLI with a local `forge-template` checkout follow
the canonical [cross-repository contributor workflow](docs/cross-repository-workflow.md).
It defines the sibling-checkout commands, local registry/schema drift check,
trust boundary, validation ladder, and safe merge/release order.

The [Data Science roadmap](docs/roadmap-v2/README.md) continues the completed
Foundation roadmap through Stages 10–14. create-forge owns its Stage 13
discovery-driven preview integration and the Stage 14 end-to-end client
rollout; component contracts and generated content remain in forge-template.
The canonical
[Data Science archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-archetype.md)
fixes the future shape and ownership boundary; create-forge must consume it
through discovery rather than reproduce its component semantics.
The canonical
[initial capability contracts](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-capabilities.md)
likewise keep Jupyter requirements and Scientific Python selection engine-
owned until generic capability selection is implemented in Stage 13.
FT-11.01 through FT-11.03 are complete: the engine publishes the
required Foundation points, Jupyter component under [forge-template ADR
0050](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0050-production-jupyter-capability.md),
and Scientific Python component under [forge-template ADR
0051](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0051-production-scientific-python-capability.md).
FT-11.04 completed their production composition validation, and Stage 12
implemented, validated, and published the `data-science` archetype in
[`forge-template 0.4.0`](https://github.com/Sandsy09/forge-template/releases/tag/v0.4.0)
([acceptance evidence](https://github.com/Sandsy09/forge-template/blob/main/docs/data-science-validation.md#published-040-release-verification)).
[CF-13.01](https://github.com/Sandsy09/create-forge/issues/106)
([ADR 0026](docs/adr/0026-adopt-the-0-4-engine-compatibility-line.md)) adopted
`forge-template>=0.4,<0.5`, so `--engine-preview` discovery now returns all
five components. CF-13.02
([ADR 0027](docs/adr/0027-generic-component-selection-conventions.md)) fixed
the generic component-selection CLI conventions in the canonical
[component selection contract](docs/component-selection.md) —
`--capability`/`--platform`/`--component-option`, precedence, prompt order,
and client-versus-engine validation ownership. CF-13.03
([ADR 0028](docs/adr/0028-discovery-driven-component-selection.md)) implemented
capability and platform selection — `pipeline.Catalogue`, the four
`--capability`/`--no-capabilities`/`--platform`/`--no-platforms` flags, and
the interactive multi-selects; CF-13.04
([ADR 0029](docs/adr/0029-per-component-option-collection.md)) added
`--component-option` and per-component option collection and typing for every
selected component; CF-13.05
([ADR 0030](docs/adr/0030-data-science-preview-pipeline-validation.md))
validated the Data Science composition through the shared pipeline against the
released engine, closing CF-EPIC-13 — see the canonical
[Data Science preview-pipeline validation](docs/data-science-preview-validation.md)
record. CF-14.01
([ADR 0031](docs/adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md))
then adopts the reviewed `0.4.1` release as the `>=0.4.1,<0.5` lower bound and
prepares create-forge `0.3.0`. CF-14.02
([ADR 0032](docs/adr/0032-validate-installed-data-science-generation.md)) now
proves both accepted compositions through the installed candidate wheel — see
the canonical
[installed Data Science validation](docs/installed-data-science-validation.md)
record. CF-14.03 owns the remaining regression matrix; CF-14.04 owns the
complete changelog and publication. Do not hard-code a capability or Data
Science rule — selection is discovery-driven and semantic validation stays
engine-owned.

## What CI runs

`.github/workflows/ci.yml` runs on every push to `main` and every pull
request:

| Job | What |
| --- | --- |
| `lint` | `pre-commit run --all-files`, then `mypy` — the exact gate that runs locally on commit |
| `test` | the fast suite, matrixed across Python 3.11–3.14 |
| `windows` | the fast suite on `windows-latest` — this tool is developed on Windows |
| `wheel` | `poe check:wheel` |
| `network` | `pytest -m network` — the `copier.yml` drift guard, plus the real `update()` end-to-end. Per [ADR 0012](docs/adr/0012-engine-dependency-update-policy.md), this is the proof a compatibility-line dependency bump (e.g. Copier) requires before `all-green` allows the merge |
| `e2e` | `pytest -m e2e` — both generation paths plus installed-candidate Data Science, real destinations, and generated-project checks ([end-to-end contract](docs/end-to-end-tests.md)) |
| `all-green` | an aggregate check; this is the one branch protection requires |

`network` and `e2e` also run on a Monday cron, independent of any push here —
`forge-template` moves on its own schedule, so a PR is not the only thing that
can surface a registry mismatch or a template regression.

## Architecture decisions

Significant decisions live in [docs/adr/](docs/adr/) as Architecture Decision
Records — why Copier over Cookiecutter, why the two-repo split, why
`unsafe=True` is safe here, and so on. Add one by copying the most recent
record and incrementing the number; records are immutable, so a decision that
changes is superseded by a new record, not an edit to an old one. `poe test`
(and standalone, `uv run poe check:adr`) checks the set stays internally
consistent — filenames, numbering, the index, and the four required headings.

The accepted future boundary with `forge-template` is recorded in
[ADR 0010](docs/adr/0010-public-engine-integration-contract.md), while the
evolving package/protocol rules live in the
[integration contract](docs/integration-contract.md). The canonical
[ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
is defined by `forge-template`; this repository will construct it only through
the [supported engine facade](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md).
The canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
keeps policy resolution upstream of effective ProjectSpec construction.
CF-09.01 ([ADR 0022](docs/adr/0022-downstream-organisation-policy-hook.md))
delivered the client-side hook that retains which selection kinds were
explicitly supplied, so explicit empty lists stay distinguishable from
absent inputs -- `spec.SelectionRequest`/`SelectionProvenance`, accepted by
`pipeline.build_generation_request` as `selection`/`provenance`. The current
CLI still consumes no policy itself and ships no resolver; see the canonical
[downstream policy-consumption contract](docs/organisation-policy-consumption.md).
Forge-template's canonical
[extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
[policy fixture](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
[compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
and [no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md)
define the remaining Stage 09 boundary: clients may select reviewed content
but may not overlay arbitrary files or treat private catalogue fixtures as a
plugin mechanism. Forge-template
[ADRs 0039–0042](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/README.md)
record those decisions.
CF-09.02 ([ADR 0023](docs/adr/0023-downstream-client-reference.md)) added
[`examples/downstream_cli.py`](examples/downstream_cli.py): a second,
independent Blueprint-style CLI over the public `forge_template` facade,
with its own compatibility bounds and its own minimal organisation-policy
resolver -- it imports no `create_forge` module at all, proven by an AST
guard rather than only stated. See the canonical
[downstream client reference](docs/downstream-client-reference.md).
[ADR 0024](docs/adr/0024-reference-client-not-framework-dependency.md)
completes the Stage 09 validation: `create-forge` is one reference client,
not a framework dependency for the engine, other clients, or generated
projects.
That API begins its compatibility contract at `forge-template` `0.2.x`.
Its canonical
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md)
checks rendered output in memory before the facade returns it. Filesystem
staging, finalisation, and command execution remain `create-forge`
responsibilities at the future cutover — the living
[filesystem generation contract](docs/filesystem-generation.md) records how
`staging.py` already implements the staging and finalisation half of that
today, behind `--engine-preview`.
The canonical
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
defines the production `library` component shipped by `forge-template` at
`0.3.0`. The canonical
[CLI Application archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
selects the optionless engine-owned `cli` archetype and derives its command
from `ProjectSpec.project.repository_name`; FT-08.04 implemented it, and
CF-08.02 ([ADR 0017](docs/adr/0017-cli-application-archetype-exposure.md))
exposes both archetypes via a discovery-driven `--archetype` option and
prompt, behind the same hidden `--engine-preview` flag.
This repository's development pair moved through `forge-template==0.3.0`
(tag `v0.3.0`), whose production catalogue is no longer empty, to a real
released range: `forge-template>=0.3.1,<0.4`, declared as the optional
`engine` extra ([#9](https://github.com/Sandsy09/create-forge/issues/9),
[ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md));
then, crossing one compatibility line,
[CF-13.01](https://github.com/Sandsy09/create-forge/issues/106)
([ADR 0026](docs/adr/0026-adopt-the-0-4-engine-compatibility-line.md)) moved
that range to `forge-template>=0.4,<0.5`, the 0.4 Data Science line.
CF-14.01 ([ADR 0031](docs/adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md))
then raises its lower bound to the reviewed `forge-template 0.4.1` release.
Stage 06 first proved an exact development package/protocol pair through the
[cross-repository engine contract tests](docs/engine-contract-tests.md), and
CF-08.02 moved that pair forward to `0.3.0`; ADR 0018 then replaced the
development pin with the first released range, resolved from PyPI, and ADR
0026 moved it to the 0.4 line. The coordinated CLI cutover -- the engine
replacing direct Copier as the default `new` path -- remains a separate,
still-unfiled decision; neither ADR 0018 nor ADR 0026 performs it.
CF-07.04 ([ADR 0015](docs/adr/0015-staged-filesystem-generation.md)) moved
the development pin forward once, within the prior unreleased `0.2.0`
contract, to adopt generated-project validation; CF-08.02
([ADR 0017](docs/adr/0017-cli-application-archetype-exposure.md)) moved it
again, to the first tagged release; ADR 0018 replaced it with the first
released range, and ADR 0026 moved that range to the 0.4 line.
[ADR 0013](docs/adr/0013-projectspec-construction-boundary.md)
and the living [ProjectSpec construction contract](docs/project-spec-construction.md)
record that adapter's shape — `spec.py` builds the wire payload, `engine.py`
is the one module that calls the facade. The canonical
[component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
likewise remains engine-owned discovery metadata rather than a schema this
repository recreates. The living
[component discovery contract](docs/component-discovery.md) records how
`engine.py` checks both protocol axes before returning those public descriptors
unchanged. [ADR 0014](docs/adr/0014-lazy-engine-reachability.md) adds
`pipeline.py` and reaches this boundary from a real command for the first
time, via the hidden `new --engine-preview` flag and a lazily-imported
module `cli.py` otherwise never touches; ADR 0015 completes that flag with
real staging and finalisation. The default `new` path, and every other
command, remain the current v0.1.x Copier/registry implementation,
authoritative until the coordinated CLI cutover.
[ADR 0016](docs/adr/0016-end-to-end-reference-client-tests.md) and the living
[end-to-end tests contract](docs/end-to-end-tests.md) close Stage 07 with
real, CI-enforced coverage of that default `new` path against a released
template.
CF-08.03 ([ADR 0019](docs/adr/0019-cli-archetype-parity-review.md)) reviewed
both archetypes for parity, confirmed the shared construction path and
engine-owned discovery hold, and generalised the legacy `library` option
derivation above to be gated by a discovered descriptor rather than a
hardcoded archetype id -- see the canonical
[ProjectSpec construction contract](docs/project-spec-construction.md) for
the current form. It also recorded, without fixing,
[#91](https://github.com/Sandsy09/create-forge/issues/91): the engine path's
prompt set was still the Copier registry's Library-shaped questions
regardless of archetype.
[#91](https://github.com/Sandsy09/create-forge/issues/91)
([ADR 0025](docs/adr/0025-engine-native-prompt-flow.md)) closed that gap:
`--engine-preview` now prompts directly from the selected archetype's own
discovered `ComponentDescriptor.options`, reads no registry data at all, and
selects the archetype before collecting any answer -- see the canonical
[CLI UX and prompting conventions](docs/cli-conventions.md) for the current
`--engine-preview` flow.
CF-08.04 ([ADR 0020](docs/adr/0020-engine-path-end-to-end-tests.md)) closed
the gap ADR 0016 left open: the engine path now has its own CI-enforced
`e2e`-marked coverage --
[`tests/test_e2e_engine_generation.py`](tests/test_e2e_engine_generation.py)
generates every discovered archetype through `--engine-preview` against the
real installed engine (Data Science with its capabilities since CF-13.05,
[ADR 0030](docs/adr/0030-data-science-preview-pipeline-validation.md)),
checks each generated lock, runs
`uv run --locked poe check`, and proves the
released-install compatibility boundary (an out-of-range engine, and no
`engine` extra at all) writes nothing -- closing
[CF-EPIC-08](https://github.com/Sandsy09/create-forge/issues/39).
Forge-template's Stage 08
[composition review](https://github.com/Sandsy09/forge-template/blob/main/docs/composition-architecture-review.md)
is released at `0.3.2`; [ADR 0021](docs/adr/0021-client-finalises-engine-lockfiles.md)
records create-forge's matching lock-finalisation boundary.
CF-09.01 / [#53](https://github.com/Sandsy09/create-forge/issues/53)
([ADR 0022](docs/adr/0022-downstream-organisation-policy-hook.md)) opened
[CF-EPIC-09](https://github.com/Sandsy09/create-forge/issues/40) by delivering
the downstream policy-consumption hook: `pipeline.build_generation_request`
accepts a `selection`/`provenance` pair built from
`spec.SelectionRequest`/`SelectionProvenance`, letting a policy-aware caller
record which selection kinds were explicit and which applied policy IDs to
carry into `ProjectSpec.provenance` -- without `create-forge` itself parsing,
merging, or reading any policy document, which stays a deliberate boundary
per the canonical
[downstream policy-consumption contract](docs/organisation-policy-consumption.md).
This unblocked [#54 / CF-09.02](https://github.com/Sandsy09/create-forge/issues/54),
completed by [ADR 0023](docs/adr/0023-downstream-client-reference.md)'s
`examples/downstream_cli.py` -- a second, independent client, not a
`create-forge` usage example, since #54 forbids depending on `create-forge`
internals; see the canonical
[downstream client reference](docs/downstream-client-reference.md). This in
turn provided the independent-client evidence used by
[#55 / CF-09.03](https://github.com/Sandsy09/create-forge/issues/55), completed
under [ADR 0024](docs/adr/0024-reference-client-not-framework-dependency.md)
as the last child of
[CF-EPIC-09](https://github.com/Sandsy09/create-forge/issues/40).
[ADR 0011](docs/adr/0011-engine-source-and-version-resolution.md), ADR 0018,
and the living [engine resolution contract](docs/engine-resolution.md)
define how that engine is sourced, overridden locally, diagnosed, and
rejected when incompatible. [ADR 0012](docs/adr/0012-engine-dependency-update-policy.md)
and the living [engine update policy](docs/engine-updates.md) define how a
compatibility-line dependency update is adopted, how a breaking line is
crossed, and what automated dependency tooling may never do unattended --
`forge-template` is now a second compatibility-line dependency alongside
`copier`, each gated independently.

The living [CLI UX and prompting conventions](docs/cli-conventions.md) define
input precedence, prompt-skipping rules, interactive/non-interactive parity,
validation ownership, and exit statuses. Changes to `cli.py`, `prompts.py`, or
their replacement at the public-engine cutover must update that contract and
its executable examples together when behavior changes.

## Commit messages

Conventional Commits (`feat:`, `fix:`, `chore:`, ...). A `commit-msg` hook
enforces this once `pre-commit install --install-hooks` has run.

## Labels

[.github/labels.toml](.github/labels.toml) is the source of truth for this
repo's issue and PR labels, and is shared with `forge-template` — the same
manifest drives both, so the two never drift into different vocabularies.
Six namespaced groups each use one colour family: `area:`, `type:`,
`priority:`, `size:`, `status:`, and `roadmap:`. Most `type:` labels mirror the
Conventional Commits prefixes above; `type:epic` and `type:decision` classify
roadmap planning rather than a single eventual commit. `good first issue`,
`help wanted`, `cross-repo`, and `breaking-change` stay unprefixed because
their repository-wide meaning is clearer without another namespace.

Apply the manifest to a repo with:

```bash
uv run poe labels:sync --dry-run                 # preview, changes nothing
uv run poe labels:sync --prune                   # apply, deleting extras
uv run python scripts/labels.py --repo Sandsy09/forge-template --prune
```

`gh label create --force` makes this idempotent — re-run it any time the
manifest changes. `tests/test_labels.py` validates the manifest's shape
(colour format, description length, no name collisions) in the fast suite.

## Releasing

`pyproject.toml`'s `version` is the single source of truth for a release's tag
— see [ADR 0009](docs/adr/0009-pyproject-as-the-single-version-source.md) for
why the release workflow itself does not choose a version bump.

1. Open a PR bumping `pyproject.toml`'s `version` and regenerating the
   changelog:

   ```bash
   uv run git-cliff --tag vX.Y.Z --output CHANGELOG.md
   ```

2. Merge it. Wait for `All checks passed` on `main`.
3. Actions → Release → Run workflow, with `dry_run` checked. Confirm the
   computed tag and generated notes in the run summary.
4. Run it again with `dry_run` unchecked. This tags `main`, pushes the tag,
   publishes the GitHub release, and -- since
   [#9](https://github.com/Sandsy09/create-forge/issues/9)
   ([ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md))
   -- publishes `create-forge` to PyPI via Trusted Publishing (OIDC; no
   stored token, gated by the `pypi` GitHub Environment). `forge-template`
   releases the same way on its own repository and schedule -- see
   [forge-template ADR 0036](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0036-publish-the-engine-to-pypi.md).
