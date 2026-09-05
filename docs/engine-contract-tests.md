# Cross-Repository Engine Contract Tests

This is the canonical executable contract for the boundary between
`create-forge` and `forge-template`. It records what Stage 06 proved as a
development-only pair, what CF-07.04 (ADR 0015) and CF-08.02 (ADR 0017)
moved that pair to, what #9 (ADR 0018) then did -- assign the first
*released* engine range -- what CF-13.01 (ADR 0026) did after that by moving
the range to the `forge-template` 0.4 compatibility line, and what CF-14.01
(ADR 0031) did by adopting its reviewed `0.4.1` release. This is what a
released `create-forge[engine]` install actually resolves.

## Supported range

| Surface | Supported value |
| --- | --- |
| `forge-template` distribution | PyPI, `create-forge`'s optional `engine` extra |
| `forge-template` range | `>=0.4.1,<0.5` (current compatible release: `0.4.1`) |
| ProjectSpec protocol | `1` |
| Component-manifest protocol | `1, 2` |

`pyproject.toml` declares `forge-template>=0.4.1,<0.5` in
`[project.optional-dependencies].engine` -- an ordinary, index-resolved,
range-bounded dependency, exactly like `copier`, `typer`, or `pydantic`, not
a `[tool.uv.sources]`-pinned commit or tag. `src/create_forge/compat.py`
holds this range as `SUPPORTED_ENGINE_RANGE`; `src/create_forge/engine.py`
checks an installed package against it with
`packaging.specifiers.SpecifierSet` rather than the exact-equality check the
development-only pair used before a real release existed.

The range has moved several times. First, Stage 06's original development
commit moved to a later one, adopted by
[CF-07.04 / #50](https://github.com/Sandsy09/create-forge/issues/50)
specifically to pick up `forge-template`'s
[generated-project validation contract](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md).
Second, that commit moved to the `v0.3.0` tag, adopted by
[CF-08.02 / #10](https://github.com/Sandsy09/create-forge/issues/10) to
reach the first tagged, production-catalogue release. Both moves were
development-only: `[project.dependencies]` was unaffected, and no engine
range was assigned. [#9](https://github.com/Sandsy09/create-forge/issues/9)
and [ADR 0018](adr/0018-pypi-distribution-and-the-first-engine-range.md)
assigned the first one, `>=0.3.1,<0.4`, once
[forge-template ADR 0036](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0036-publish-the-engine-to-pypi.md)
made `0.3.1` -- a packaging-only patch over the same `0.3.0` production
catalogue -- installable from PyPI. Then
[CF-13.01 / #106](https://github.com/Sandsy09/create-forge/issues/106)
([ADR 0026](adr/0026-adopt-the-0-4-engine-compatibility-line.md)) crossed one
compatibility line, moving the range to `>=0.4,<0.5` and rerunning this
contract against it.

[CF-14.01 / #111](https://github.com/Sandsy09/create-forge/issues/111)
([ADR 0031](adr/0031-adopt-the-reviewed-forge-template-0-4-1-release.md))
then raises the lower bound within that line to the provider-reviewed `0.4.1`
release and reruns this same contract against the PyPI artefact.

Any package version outside the range fails closed. `0.4.1` is both the
declared lower bound and the current compatible release; `0.4.0` is rejected.
The [engine update policy](engine-updates.md)'s adoption rule governs later
`0.4.x` patches.

`forge-template 0.4.0` is
[published](https://pypi.org/project/forge-template/0.4.0/) as the
five-component Data Science catalogue. Its public facade and protocol tuples
are unchanged from `0.3.2` -- the source diff is empty -- so this contract's
public-facade coverage carried across the move without a signature change.
The reviewed `0.4.1` package republishes that production catalogue, public
facade, protocols, and rendered bytes unchanged; the provider's canonical
[reviewed-release record](https://github.com/Sandsy09/forge-template/blob/main/docs/reviewed-engine-release.md)
is the release evidence.

## What the executable contract proves

[`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py)
exercises the installed engine through `src/create_forge/engine.py`. Together
with the focused adapter and guard suites, it proves that:

- the installed package falls within the range above and advertises the
  protocol pair above;
- package and relevant protocol compatibility are checked before parsing,
  discovery, validation, or rendering calls reach the engine, at both edges
  of the range (below the lower bound, at the excluded upper bound);
- malformed ProjectSpec and invalid component selections remain structured,
  engine-owned failures;
- discovery returns the installed production catalogue without registry
  fallback;
- the installed 0.4 line exposes the previous line's `library` and `cli`
  archetypes *and* the new descriptor shapes it added -- at least one
  `capability`-kind descriptor and at least one declaring a `requires`
  relationship -- asserted by descriptor kind and relationship shape, never
  by a component id this repository must not copy (ADR 0026);
- rendering returns immutable in-memory files, already validated by
  `forge_template.validate_rendered_project`, and never owns destination
  writes; and
- the adapter imports only names re-exported by the top-level public
  `forge_template` facade.

The production catalogue ships `library` and `cli`, since
[forge-template FT-08.02 / #41](https://github.com/Sandsy09/forge-template/issues/41)
migrated the Library archetype and FT-08.04 added the CLI Application
archetype in the `0.3.0` release, and adds the `data-science` archetype plus
the `jupyter` and `scientific-python` capabilities in the `0.4.0` release the
declared range now resolves. The client-side rendering assertion is a real
public-facade call that succeeds for either reference archetype and returns
real files.
`create-forge` still does not import `forge-template`'s private
fixture-catalogue seam or its own
[`tests/test_composition_contract.py`](https://github.com/Sandsy09/forge-template/blob/main/tests/test_composition_contract.py)
goldens; this contract proves the public facade only.

This installable, range-assigned engine is what closed
[CF-07.06 / #51](https://github.com/Sandsy09/create-forge/issues/51)'s
[end-to-end suite](end-to-end-tests.md)'s engine-path blocker:
[CF-08.04 / #85](https://github.com/Sandsy09/create-forge/issues/85), under
[CF-EPIC-08](https://github.com/Sandsy09/create-forge/issues/39), wrote that
coverage against `create-forge[engine]` --
[`tests/test_e2e_engine_generation.py`](../tests/test_e2e_engine_generation.py)
(ADR 0020) drives the real `create-forge` console script's `--engine-preview`
path in CI, generating both archetypes and proving the same package-range
boundary this contract proves in-process. This file still proves the public
facade compiles and negotiates correctly in isolation, distinct from -- and a
cheaper complement to -- that end-to-end coverage.

## Validate a sibling checkout

The normal fast suite uses the released PyPI package resolved into
`uv.lock`. To validate pending sibling changes ahead of a new
`forge-template` release, install both working trees into an isolated
environment and run the same focused contract file:

```bash
uv run --no-project --isolated --with . --with ../forge-template --with pytest python -m pytest -o addopts= tests/test_engine_cross_repository.py
```

Local path builds include current working-tree source, including uncommitted
changes, and override the released PyPI resolution for that one run only --
no `pyproject.toml` or `uv.lock` change is needed or made. The sibling
package must satisfy `>=0.4.1,<0.5`; a version outside that range is
unsupported and fails until the declared range, contract, and tests are moved
together. The broader
[cross-repository contributor workflow](cross-repository-workflow.md) defines
the remaining validation and release order.

If the sibling checkout has moved (a new commit, or edited source files)
since the last time this command ran in the same environment, add
`--no-cache` -- `uv run --with <local-path>` has been observed reusing a
previously built archive for that path without detecting the source change,
which silently tests against old sibling code rather than the one intended.

## Adopting a new compatible release

A `forge-template` release inside the declared `>=0.4.1,<0.5` range (`0.4.1`
today; a later `0.4.x` patch while `0.4.x` stays the compatibility line) may
be adopted once this contract passes against it, per the sibling-checkout
validation above and the [engine update policy](engine-updates.md). A release
that would require a minor bump -- pre-1.0, that is itself a new
compatibility line -- follows
[ADR 0012](adr/0012-engine-dependency-update-policy.md)'s full sequence,
worked through once already by
[ADR 0026](adr/0026-adopt-the-0-4-engine-compatibility-line.md): move the
range in `pyproject.toml`, this document's table, and
`docs/integration-contract.md`'s compatibility table together, and prove the
new range against both its lower bound and the previous line's latest release
before merging.
