# Add capabilities

Capabilities add tooling or dependencies to a project. Select one
archetype, then zero or more compatible capabilities. The engine currently
provides `jupyter` and `scientific-python`; both are optionless. The
catalogue also ships one platform component, `github`, selected separately
with `--platform` — see below.

## Jupyter for a library

Use this when notebooks help you explore or demonstrate a package without
needing the Data Science starter layout:

```bash
uvx create-forge new "Exploration Lib" --archetype library --capability jupyter --yes --data license=mit
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
uvx create-forge new "Analysis Tools" --archetype cli --capability scientific-python --yes --data license=mit
cd analysis-tools
uv run --locked poe check
uv run analysis-tools hello Analyst
```

The project has NumPy, pandas, Matplotlib, and scikit-learn runtime
dependencies and an import test. Add your analysis functions to the package
and call them from a new Typer command. Scientific Python does not require
Jupyter or add notebook tooling.

For an interactive application instead, see
[Add the scientific stack](streamlit.md#add-the-scientific-stack) on the
Streamlit page.

## GitHub platform for automated dependency updates

`github` is a platform component: it adds a GitHub repository, CI workflow,
and issue/pull-request templates. The `dependabot` capability requires it —
select both together with `--platform`:

```bash
uvx create-forge new "My Lib" --archetype library --platform github --capability dependabot --yes --data license=mit
```

This adds weekly, GitHub-native dependency-update configuration on top of the
GitHub platform's own workflow and templates. Selecting `dependabot` without
`--platform github` fails before a project is written, the same way
selecting Data Science without Jupyter does.

## Selection rules

- Repeat `--capability ID` to select several capabilities.
- Data Science requires an explicit `--capability jupyter` under `--yes`.
  Interactive selection preselects and locks required capabilities.
- `--no-capabilities` explicitly selects none; it conflicts with
  `--capability` and cannot satisfy Data Science's Jupyter requirement.
- With `--yes`, supply `--archetype`; omitted optional capabilities remain
  unselected. The CLI does not guess additional selections.
- Non-interactive generation also requires `--data license=VALUE`. These
  recipes use `mit`; choose `proprietary` or `apache-2.0` instead when
  appropriate for your project. The interactive flow asks this question.
- `--platform` selects a discovered platform (repeatable, like
  `--capability`); `--no-platforms` explicitly selects none and conflicts
  with `--platform`. `github` is the catalogue's one platform today; see
  [GitHub platform for automated dependency updates](#github-platform-for-automated-dependency-updates)
  above.

Invalid or incompatible selections fail before a project is written.
Choose from the interactive engine catalogue (`create-forge list`);
`list --legacy` shows the separate Copier registry.

## Component options

Options belong to a selected component and use its ID as a prefix:

```bash
uvx create-forge new "Versioned Lib" --archetype library --capability jupyter --component-option library.packaging_mode=hatchling-static --component-option library.initial_version=0.2.0 --yes --data license=mit
```

This selects Library's packaging and initial version without changing
Jupyter. See [Library options](library.md#library) for accepted values.
Options for unselected components, unknown options, and invalid values are
rejected. CLI Application, Data Science, Streamlit, Jupyter, and Scientific
Python currently expose no options.

The CLI consumes the engine's bundled catalogue. Installing an arbitrary
Python package does not register a Forge capability. Request new
capabilities through the [template issue tracker](https://github.com/Sandsy09/forge-template/issues/new/choose).
