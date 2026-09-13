# Choose a project type

`create-forge new` uses the engine by default. Pick an archetype, add
capabilities if you need them, and `update` works the same way afterward.
The direct Copier route (`--legacy`) remains available and fully
supported, unaffected by any of this.

| Archetype | Generated starting point | Template updates |
| --- | --- | --- |
| [Library](library.md) | Installable package, configurable packaging, Git hooks | `create-forge update` |
| [CLI Application](cli-application.md) | Typer command, `python -m` entry point, command tests | `create-forge update` |
| [Data Science](data-science.md) | Package, starter notebook, ignored working-data paths | `create-forge update` |
| [Legacy Copier library](library.md#legacy-copier-library-legacy) | Installable package, shared checks, three packaging modes | `create-forge update` (Copier route) |

## What every archetype shares

Every archetype includes a `src/` package, `pyproject.toml`, `uv.lock`,
Ruff, mypy, pytest, and Poe tasks, plus README, contribution, and security
guidance. Each adds its own project structure on top.

`new` resolves the engine, renders the project, creates `uv.lock`, then
initialises Git, makes the initial commit, and — if a `.pre-commit-config.yaml`
was rendered — installs pre-commit hooks. The first `uv run --locked poe
check` installs remaining development dependencies and runs checks.

The Library archetype's packaging choice is a component option (see
below); CLI Application and Data Science are currently optionless beyond
their capabilities.

## Add capabilities

| Capability | Useful when | Adds |
| --- | --- | --- |
| Jupyter | You explore a package or analyse data in notebooks | JupyterLab, a Python kernel, notebook checks and tasks |
| Scientific Python | Your project uses numerical or tabular analysis | NumPy, pandas, Matplotlib, scikit-learn, and an import test |

Either capability can accompany any archetype. Data Science requires
Jupyter; it is not added silently to non-interactive commands. Scientific
Python remains independently optional. Jupyter alone does not create a
starter notebook; Data Science supplies that file.

Choose one archetype interactively:

```bash
uvx create-forge new
```

The CLI offers the archetypes and capabilities supplied by the installed
engine — run `create-forge list` to see the discovered catalogue.
`list --legacy` shows the separate, bundled Copier registry. There are no
platform components in the current engine catalogue.

Non-interactive recipes explicitly choose a license with `--data license=mit`.
Replace it with `proprietary` or `apache-2.0` to match your project.
Under `--yes`, an omitted license answer is not filled in for you.

Follow the [capability recipes](capabilities.md) for explicit selections.
