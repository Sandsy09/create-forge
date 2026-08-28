# Cross-Repository Engine Contract Tests

This is the canonical executable contract for the development-only boundary
between `create-forge` and `forge-template`. It records what Stage 06 proves
before the public engine is installed by, or reachable from, a released CLI.

## Tested development pair

| Surface | Tested value |
| --- | --- |
| `forge-template` package | `0.2.0` |
| Source | `2158c85a46efffc7d8ea2d43e347b943359baed1` |
| ProjectSpec protocol | `1` |
| Component-manifest protocol | `1` |

`pyproject.toml` declares `forge-template==0.2.0` only in the `engine`
development group and maps it to the full immutable source revision above.
This exact pair is not a released compatibility range: the runtime dependency
and its tested lower/upper bounds remain unassigned until
[PyPI/distribution issue #9](https://github.com/Sandsy09/create-forge/issues/9)
and the atomic CLI cutover in
[CF-07.01 / #49](https://github.com/Sandsy09/create-forge/issues/49).

Until then, any other package version fails closed. Adopting even a nominally
compatible `0.2.x` development version requires updating the pin, this table,
and the contract tests together.

## What the executable contract proves

[`tests/test_engine_cross_repository.py`](../tests/test_engine_cross_repository.py)
exercises the installed engine through `src/create_forge/engine.py`. Together
with the focused adapter and guard suites, it proves that:

- the installed package advertises the exact package and protocol pair above;
- package and relevant protocol compatibility are checked before parsing,
  discovery, validation, or rendering calls reach the engine;
- malformed ProjectSpec and invalid component selections remain structured,
  engine-owned failures;
- discovery returns the installed production catalogue without registry
  fallback;
- rendering returns immutable in-memory files and never owns destination
  writes; and
- the adapter imports only names re-exported by the top-level public
  `forge_template` facade.

The production catalogue is intentionally empty until
[forge-template FT-08.02 / #41](https://github.com/Sandsy09/forge-template/issues/41)
migrates the Library archetype. Therefore the current client-side rendering
assertion is a real public-facade call that fails with
`invalid-component-selection` and leaves the filesystem untouched. Successful
composition and rendering are already proven inside `forge-template` by its
[`tests/test_composition_contract.py`](https://github.com/Sandsy09/forge-template/blob/main/tests/test_composition_contract.py)
goldens. `create-forge` does not import their private fixture-catalogue seam.

## Validate a sibling checkout

The normal fast suite uses the immutable Git source in `uv.lock`. To validate
pending sibling changes, install both working trees into an isolated
environment and run the same focused contract file:

```bash
uv run --no-project --isolated --with . --with ../forge-template --with pytest python -m pytest -o addopts= tests/test_engine_cross_repository.py
```

Local path builds include current working-tree source, including uncommitted
changes. The sibling package must still declare version `0.2.0`; a version
bump is a new development pair and must be adopted explicitly. The broader
[cross-repository contributor workflow](cross-repository-workflow.md) defines
the remaining validation and release order.

## Cutover boundary

CF-07.01 replaces the exact development assertion with the first installable,
bounded engine dependency only after #9 selects a distribution channel. That
change must test the declared lower bound and a representative latest
compatible release, update the integration compatibility table, and keep the
same fail-before-side-effects behavior. Stage 06 does not pre-assign those
values.
