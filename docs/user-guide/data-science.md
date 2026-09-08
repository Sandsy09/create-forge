# Start a Data Science project

Use Data Science when notebooks explore reusable Python code. The preview
creates a package, tests, and an output-free starter notebook. Jupyter is
required; the scientific runtime stack is optional.

## Start with notebooks and a package

```bash
uvx --from "create-forge[engine]==0.3.2" create-forge new "Notebook Study" --engine-preview --archetype data-science --capability jupyter --yes --data license=mit
cd notebook-study
uv run --locked poe check
uv run poe notebook
```

The final command starts JupyterLab. Open `notebooks/getting-started.ipynb`.
Put reusable functions in `src/notebook_study/` and tests in `tests/`, then
import the package from your notebooks. Stop the server with Ctrl+C when
finished.

## Include the scientific stack

For numerical work, data frames, charts, or machine learning, generate a
second project with Scientific Python selected:

```bash
uvx --from "create-forge[engine]==0.3.2" create-forge new "Model Study" --engine-preview --archetype data-science --capability jupyter --capability scientific-python --yes --data license=mit
cd model-study
uv run --locked poe check
uv run poe notebook
```

This also installs NumPy, pandas, Matplotlib, and scikit-learn as runtime
dependencies and includes a test that imports them. No dataset, model,
training pipeline, or deployment platform is generated.

## Working files

| Location | Intended contents |
| --- | --- |
| `src/<package>/` | Reusable Python code |
| `tests/` | Tests for package behaviour |
| `notebooks/` | Exploratory and reporting notebooks |
| `data/raw/` | Source data as received |
| `data/interim/` and `data/processed/` | Intermediate and prepared datasets |
| `models/` | Trained or serialised models |
| `artifacts/` | Generated figures, reports, and outputs |

The data, model, and artifact directories are ignored by Git and are not
created during generation. Create them when needed. Keep credentials,
datasets, and generated binaries out of version control.

## Check notebooks before committing

Clear notebook outputs and execution counts, then run:

```bash
uv run --locked poe notebook:check
uv run --locked poe check
```

Notebook validation checks stored notebook content before executing
temporary copies with the project's kernel. It leaves source notebooks
unchanged. Execution is not sandboxed: only run notebooks you trust, since
they have your user's filesystem and network access.

`poe check` already includes the notebook check, so use the dedicated task
when you only need to validate notebooks. Both Data Science compositions
are preview projects and cannot use `create-forge update`.
