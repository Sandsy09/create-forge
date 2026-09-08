# Choose a project type

Start with the default Library workflow if you want configurable repository
tooling and future Copier template updates. Use the engine preview to try
CLI applications, notebook-oriented projects, or composable capabilities.

| Workflow | Generated starting point | Template updates |
| --- | --- | --- |
| [Default Library](library.md#default-library) | Installable package, configurable checks, Git hooks, GitHub Actions, optional docs | `create-forge update` |
| [Preview Library](library.md#preview-library) | Installable package, shared checks, three packaging modes | Not supported |
| [Preview CLI Application](cli-application.md) | Typer command, `python -m` entry point, command tests | Not supported |
| [Preview Data Science](data-science.md) | Package, starter notebook, ignored working-data paths | Not supported |

## What preview projects share

All three preview archetypes include a `src/` package, `pyproject.toml`,
`uv.lock`, Ruff, mypy, pytest, and Poe tasks. They include README,
contribution, and security guidance. Each adds its own project structure.

Preview generation writes a project and resolves its lockfile. It does not
initialise Git, install hooks, or generate the default template's CI
workflows. The first `uv run --locked poe check` installs dependencies and
runs checks. Initialise and commit a Git repository yourself when ready.

The default Library's switches for type-checking, docs, dependency bots,
and other repository tooling are not preview options. Preview Library
offers packaging choices; CLI Application and Data Science are currently
optionless archetypes.

## Add capabilities

| Capability | Useful when | Adds |
| --- | --- | --- |
| Jupyter | You explore a package or analyse data in notebooks | JupyterLab, a Python kernel, notebook checks and tasks |
| Scientific Python | Your project uses numerical or tabular analysis | NumPy, pandas, Matplotlib, scikit-learn, and an import test |

Either capability can accompany any preview archetype. Data Science
requires Jupyter; it is not added silently to non-interactive commands.
Scientific Python remains independently optional. Jupyter alone does not
create a starter notebook; Data Science supplies that file.

Choose one archetype interactively:

```bash
uvx --from "create-forge[engine]==0.3.2" create-forge new --engine-preview
```

The CLI offers the archetypes and capabilities supplied by the installed
engine. `create-forge list` continues to show only the default Copier
registry. There are no platform components in the current engine catalogue.

Non-interactive recipes explicitly choose a license with `--data license=mit`.
Replace it with `proprietary` or `apache-2.0` to match your project. Unlike
the default Copier path, preview generation under `--yes` does not fill in
an omitted license answer.

Follow the [capability recipes](capabilities.md) for explicit selections
and the [installation guide](installation.md) to pin the engine version.
