# Build a Python library

Use Library for reusable code that you want to import from other projects
or distribute as a wheel. Both workflows produce a `src/` package and
tests; choose the workflow based on its tooling and update support.

## Default Library

This example creates `credit-risk-utils/` with an import package named
`credit_risk_utils`, Hatchling packaging, and a static version:

```bash
uvx create-forge@0.3.0 new "Credit Risk Utils" --template library --ref v0.4.1 --yes --data github_org=example-org --data build_backend=hatchling --data versioning=static
cd credit-risk-utils
uv run poe check
uv build
```

Configure your [Git identity](index.md#before-you-start) first and replace
the example organisation before using the generated repository settings.
The template initialises Git, installs dependencies, and installs hooks.
`uv build` writes a wheel and source archive under `dist/`; it does not
publish either one.

Add your implementation to `src/credit_risk_utils/` and tests under `tests/`.
You can pull later template changes with [Copier updates](updates.md).

### Packaging and tooling choices

| Choice | Default-workflow answers |
| --- | --- |
| uv build backend, static version | `--data build_backend=uv_build --data versioning=static` |
| Hatchling, static version | `--data build_backend=hatchling --data versioning=static` |
| Hatchling, Git-tag version | `--data build_backend=hatchling --data versioning=vcs` |

uv's build backend supports static versioning here. Git-derived versions
require Hatchling; choose `vcs` when releases will be identified by Git tags.

Other useful presets are `--data type_checking=both`,
`--data use_docs=true`, `--data license=mit`, and
`--data dependency_updates=dependabot`. Omit `--yes` to choose interactively.
When docs are enabled, `uv run poe docs` serves the generated project's own
documentation and `uv run poe docs:build` validates it.

## Preview Library

Use this route to combine a distributable package with the engine's
[capabilities](capabilities.md). It does not support template updates.

```bash
uvx --from "create-forge[engine]==0.3.0" create-forge new "Preview Lib" --engine-preview --archetype library --yes --component-option library.packaging_mode=hatchling-static --data license=mit
cd preview-lib
uv run --locked poe check
uv build
```

This creates `src/preview_lib/`, package tests, shared quality tooling, and
`uv.lock`. It leaves Git initialisation to you. The first useful change is
adding a function and its test, then rerunning `poe check`.

| Library option | Values |
| --- | --- |
| `library.packaging_mode` | `uv-build-static` (default), `hatchling-static`, `hatchling-vcs` |
| `library.initial_version` | A PEP 440 version; defaults to `0.1.0` |

Set options with repeated `--component-option ID.OPTION=VALUE` flags.
`initial_version` is ignored in `hatchling-vcs` mode, where Git tags determine
the build version. For that mode, initialise Git, commit the generated files,
and create your intended version tag before building a release.
