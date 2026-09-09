# create-forge

[![CI](https://github.com/Sandsy09/create-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/Sandsy09/create-forge/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/create-forge)](https://pypi.org/project/create-forge/)

Create Python projects with packaging, quality checks, and a useful starting
structure already in place.

```bash
uvx create-forge new
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/), Git,
and Python 3.11+ (uv can install Python for you). Configure your Git author
name and email before generating a default Library project: generation
creates local commits.

**[Read the Forge user guide](https://sandsy09.github.io/create-forge/)**
for walkthroughs, template choices, and troubleshooting.

## How the repositories fit together

| Repository | What it provides |
| --- | --- |
| **create-forge** | The CLI: prompts, project creation, updates, and diagnostics. |
| [forge-template](https://github.com/Sandsy09/forge-template) | The project templates and composition engine used to generate files. |

You normally use the CLI without cloning either repository. Generated
projects do not depend on either Forge package at runtime.

## Create your first project

```bash
uvx create-forge new "My Library"
cd my-library
uv run poe check
```

The default workflow creates an installable Library with a `src/` layout,
uv, Ruff, pytest with coverage, mypy and/or pyright, pre-commit hooks, and
GitHub Actions CI. Choose your build backend, versioning, license, and
dependency-update tooling. MkDocs documentation is optional.

The template is rendered by [Copier](https://copier.readthedocs.io/), which
also supports bringing later template improvements into existing projects.

## Install and manage the tool

Use `uvx` for occasional runs, or install a persistent command:

```bash
uv tool install create-forge
create-forge new
uv tool upgrade create-forge
```

If the command is not on your PATH, run `uv tool update-shell` and restart
your terminal.

### Choose a CLI version

```bash
uvx create-forge@latest new
uvx create-forge@0.3.2 new
uv tool install "create-forge==0.3.2"
```

Plain `uvx create-forge` can reuse a cached or persistently installed
version; `@latest` explicitly requests the latest release. Tool upgrades
respect the constraints used at installation, so an exact pin stays pinned.
To return to the latest release, run `uv tool install create-forge@latest`.
See [installation and versions](https://sandsy09.github.io/create-forge/installation/).

## Everyday usage

| Command | Purpose |
| --- | --- |
| `uvx create-forge new` | Create a project interactively. |
| `uvx create-forge list` | List the bundled Copier templates. |
| `uvx create-forge update` | Update a Copier-generated project from its directory. |
| `uvx create-forge doctor` | Diagnose Python, Git, uv, and package compatibility. |
| `uvx create-forge config init` | Create an optional configuration file. |
| `uvx create-forge config show` | Show resolved configuration and its sources. |

For scripts and CI, provide a project name and skip questions with `--yes`:

```bash
uvx create-forge new "My Library" --yes --data github_org=your-org --data build_backend=hatchling --data versioning=vcs
```

Use `--path` to choose the destination and repeat `--data key=value` to
preset answers. Run `uvx create-forge new --help` for the default workflow's
options. Saved author details, GitHub organisation, and preferred template
are covered in the [CLI guide](https://sandsy09.github.io/create-forge/cli/).

### Choose a template version or source

```bash
uvx create-forge new "My Library" --template library --ref v0.4.1
uvx create-forge new "Custom Project" --template-url https://github.com/you/your-template
```

`--ref` selects a Git revision in the **template repository**. It does not
select the CLI version. Without it, Copier uses the latest suitable release
tag. The bundled registry currently offers Library; upgrade the CLI to
receive registry changes.

Templates can execute code through generation and update tasks. Use custom
sources only when you trust their content; `--yes` also skips the custom
template confirmation.

### Update a generated project

From a clean, committed Copier-generated project:

```bash
uvx create-forge update --dry-run
uvx create-forge update
uv run poe check
```

Keep `.copier-answers.yml` committed. Review the resulting diff and resolve
conflicts before committing. A dry run validates the update without applying
it; it does not produce a file-by-file diff. Use `update --ref v0.4.1` to
target a particular template version.

## Preview: more project types and capabilities

The `0.3.2` CLI also provides an opt-in engine preview using
`forge-template>=0.4.1,<0.5`. These options are currently hidden from help.

| Project type | Use it for |
| --- | --- |
| Library | A distributable Python package with a choice of packaging modes. |
| CLI Application | A Typer application with a console command and tests. |
| Data Science | A Python package with a starter notebook and Jupyter tooling. |

Add **Jupyter** for notebook development or **Scientific Python** for NumPy,
pandas, Matplotlib, and scikit-learn. Data Science requires Jupyter;
Scientific Python is optional. These capabilities can also accompany the
other preview archetypes.

```bash
uvx --from "create-forge[engine]==0.3.2" create-forge new "My Analysis" --engine-preview --archetype data-science --capability jupyter --yes --data license=mit
cd my-analysis
uv run --locked poe check
uv run poe notebook
```

For regular preview use, install with `uv tool install "create-forge[engine]"`.
The [project guide](https://sandsy09.github.io/create-forge/projects/) explains
each type's output and links to complete recipes.

**Preview projects do not support `create-forge update`.** Their shared
tooling differs from the default Copier template; the preview does not
generate its CI workflows or install Git hooks. `--template`,
`--template-url`, and `--ref` apply only to the Copier workflow.

## What's next

The Foundation and Data Science roadmaps are complete. The filed
[Engine-Default Cutover](docs/roadmap-v3/README.md) and
[Streamlit Archetype](docs/roadmap-v4/README.md) roadmaps describe future work;
their issues are open, and no release is scheduled. Working engine
updates and a supported legacy Copier route must precede the default switch.
Follow [open work](https://github.com/Sandsy09/create-forge/issues)
and [releases](https://github.com/Sandsy09/create-forge/releases) for updates,
or suggest a project type, capability, or guide you would find useful.

## Feedback and contributing

- [Report a CLI problem or suggest a feature](https://github.com/Sandsy09/create-forge/issues/new/choose).
- [Request or correct documentation](https://github.com/Sandsy09/create-forge/issues/new?template=documentation.yml).
- [Report generated-content or capability problems](https://github.com/Sandsy09/forge-template/issues/new/choose).

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and PR checks, and
the [reference index](https://sandsy09.github.io/create-forge/reference/) for
engine APIs and architecture documents. Report vulnerabilities through
[SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
