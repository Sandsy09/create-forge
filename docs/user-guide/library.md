# Build a Python library

Use the `library` archetype for reusable code that you want to import from
other projects or distribute as a wheel.

## Library

This example creates `credit-risk-utils/` with an import package named
`credit_risk_utils`, Hatchling packaging, and a static version:

```bash
uvx create-forge new "Credit Risk Utils" --archetype library --yes --component-option library.packaging_mode=hatchling-static --data license=mit
cd credit-risk-utils
uv run --locked poe check
uv build
```

Configure your [Git identity](index.md#before-you-start) first. `new`
resolves the engine, creates `src/credit_risk_utils/`, package tests, a
`uv.lock`, initialises Git, makes the initial commit, and (if selected)
installs pre-commit hooks. `uv build` writes a wheel and source archive
under `dist/`; it does not publish either one.

Add your implementation to `src/credit_risk_utils/` and tests under
`tests/`. Pull later template changes with `create-forge update` — see
[project updates](updates.md).

### Packaging choices

| Library option | Values |
| --- | --- |
| `library.packaging_mode` | `uv-build-static` (default), `hatchling-static`, `hatchling-vcs` |
| `library.initial_version` | A PEP 440 version; defaults to `0.1.0` |

Set options with repeated `--component-option ID.OPTION=VALUE` flags.
`initial_version` is ignored in `hatchling-vcs` mode, where Git tags
determine the build version — for that mode, commit the generated files and
create your intended version tag before building a release. Omit `--yes`
to choose interactively; see [capabilities](capabilities.md) to add
Jupyter or a scientific Python stack.

## Legacy Copier library (`--legacy`)

The direct Copier route remains available and fully supported, unaffected
by the archetype above — install the `legacy` extra first (see
[installation](installation.md)):

```bash
uvx create-forge new "Credit Risk Utils" --legacy --template library --ref v0.4.1 --yes --data github_org=example-org --data build_backend=hatchling --data versioning=static
cd credit-risk-utils
uv run poe check
uv build
```

Replace the example organisation before using the generated repository
settings. `new --legacy` initialises Git, installs dependencies, and
installs hooks. Pull later Copier template changes with `create-forge
update` (routed automatically since this project records
`.copier-answers.yml`) — see [project updates](updates.md).

### Packaging and tooling choices

| Choice | Answers |
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
