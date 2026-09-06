# Add capabilities

Capabilities add tooling or dependencies to a preview project. Select one
archetype, then zero or more compatible capabilities. The engine currently
provides `jupyter` and `scientific-python`; both are optionless.

## Jupyter for a library

Use this when notebooks help you explore or demonstrate a package without
needing the Data Science starter layout:

```bash
uvx --from "create-forge[engine]==0.3.0" create-forge new "Exploration Lib" --engine-preview --archetype library --capability jupyter --yes --data license=mit
cd exploration-lib
uv run --locked poe check
uv run poe notebook
```

This adds JupyterLab, the Python kernel, and notebook validation tasks.
Create your own notebook in `notebooks/` through JupyterLab; the capability
does not create one. Clear stored outputs and execution counts before
running `uv run --locked poe notebook:check`. Read the
[notebook execution guidance](data-science.md#check-notebooks-before-committing).

## Scientific Python for a CLI

Use this when a command-line application performs numerical or tabular
analysis without notebooks:

```bash
uvx --from "create-forge[engine]==0.3.0" create-forge new "Analysis Tools" --engine-preview --archetype cli --capability scientific-python --yes --data license=mit
cd analysis-tools
uv run --locked poe check
uv run analysis-tools hello Analyst
```

The project has NumPy, pandas, Matplotlib, and scikit-learn runtime
dependencies and an import test. Add your analysis functions to the package
and call them from a new Typer command. Scientific Python does not require
Jupyter or add notebook tooling.

## Selection rules

- Repeat `--capability ID` to select several capabilities.
- Data Science requires an explicit `--capability jupyter` under `--yes`.
  Interactive selection preselects and locks required capabilities.
- `--no-capabilities` explicitly selects none; it conflicts with
  `--capability` and cannot satisfy Data Science's Jupyter requirement.
- With `--yes`, supply `--archetype`; omitted optional capabilities remain
  unselected. The CLI does not guess additional selections.
- Non-interactive preview generation also requires `--data license=VALUE`.
  These recipes use `mit`; choose `proprietary` or `apache-2.0` instead when
  appropriate for your project. The interactive flow asks this question.
- `--platform` and `--no-platforms` are preview selection flags, but no
  platform components are currently shipped.

Invalid or incompatible selections fail before a project is written.
Choose from the interactive engine catalogue; `create-forge list` shows
the separate Copier registry.

## Component options

Options belong to a selected component and use its ID as a prefix:

```bash
uvx --from "create-forge[engine]==0.3.0" create-forge new "Versioned Lib" --engine-preview --archetype library --capability jupyter --component-option library.packaging_mode=hatchling-static --component-option library.initial_version=0.2.0 --yes --data license=mit
```

This selects Library's packaging and initial version without changing
Jupyter. See [Library options](library.md#preview-library) for accepted
values. Options for unselected components, unknown options, and invalid
values are rejected. CLI Application, Data Science, Jupyter, and Scientific
Python currently expose no options.

The CLI consumes the engine's bundled catalogue. Installing an arbitrary
Python package does not register a Forge capability. Request new
capabilities through the [template issue tracker](https://github.com/Sandsy09/forge-template/issues/new/choose).
