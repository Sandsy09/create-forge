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
name and email before generating a project: generation creates local commits.

**[Read the Forge user guide](https://sandsy09.github.io/create-forge/)**
for walkthroughs, project types, and troubleshooting. Coming from a `0.3.x`
install or project? Start with the
[migration guide](https://sandsy09.github.io/create-forge/migration/).

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

`new` discovers project types and capabilities directly from the
`forge-template` engine, constructs a ProjectSpec, and renders through its
public facade — no template repository to clone. Generation also runs
`git init`, an initial commit, and installs any pre-commit hooks the project
carries.

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
uvx create-forge@0.5.0 new
uv tool install "create-forge==0.5.0"
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
| `uvx create-forge list` | List the discovered project types and capabilities. |
| `uvx create-forge update` | Update a generated project from its directory. |
| `uvx create-forge doctor` | Diagnose Python, Git, uv, and package compatibility. |
| `uvx create-forge config init` | Create an optional configuration file. |
| `uvx create-forge config show` | Show resolved configuration and its sources. |

For scripts and CI, provide a project name and skip questions with `--yes`:

```bash
uvx create-forge new "My Library" --yes --data github_org=your-org --data build_backend=hatchling --data versioning=vcs
```

Use `--path` to choose the destination, `--archetype`/`--capability` to
preselect a project type, and repeat `--data key=value` to preset answers.
Run `uvx create-forge new --help` for the default workflow's options. Saved
author details, GitHub organisation, and preferred archetype are covered in
the [CLI guide](https://sandsy09.github.io/create-forge/cli/).

### More project types and capabilities

```bash
uvx create-forge new "My Analysis" --archetype data-science --capability jupyter --yes --data license=mit
cd my-analysis
uv run --locked poe check
uv run poe notebook
```

Available types include Library, CLI Application, Data Science (a Python
package with a starter notebook and Jupyter tooling), and Streamlit (an
installable package with an interactive Streamlit application, from
`create-forge 0.5.0`), plus optional
**Jupyter** and **Scientific Python** capabilities (Data Science requires
Jupyter; Scientific Python is optional and can accompany any archetype). The
[project guide](https://sandsy09.github.io/create-forge/projects/) explains
each type's output.

### Isolated engine overrides

```bash
uvx create-forge new "Custom" --engine-source https://github.com/you/your-engine-fork --engine-ref v0.5.1
```

`--engine-source`/`--engine-ref` provision an isolated environment for
cross-repository development against a fork or unreleased engine revision,
separate from your ordinary install. Use custom sources only when you trust
their content; `--yes` also skips the confirmation prompt.

### Update a generated project

```bash
uvx create-forge update --dry-run
uvx create-forge update
uv run poe check
```

`update` runs the engine-native Git-backed three-way merge against the
project's committed `.forge/generation.json`. Review the resulting diff and
resolve any conflict markers before committing. `--dry-run` prints the
per-target classification without writing anything. A failed or interrupted
update leaves a working tree you can restore to your last commit — the
[updates guide](https://sandsy09.github.io/create-forge/updates/) has the
recovery procedure, including for an update that is already staged.

## The `--legacy` Copier route

```bash
uv tool install "create-forge[legacy]"
uvx --from "create-forge[legacy]" create-forge new "My Library" --legacy --template library --ref v0.4.1
```

`--legacy` renders directly from the bundled Copier registry instead of the
engine — the original `create-forge` architecture, still fully supported.
`--template`, `--template-url`, and `--ref` select the template and version
under this route; `create-forge update` against a `.copier-answers.yml`
project runs `copier update`. The `legacy` extra installs `copier`; without
it, `--legacy` exits `3` naming the remedy.

## What's next

The Foundation, Data Science, and Engine-Default Cutover roadmaps are
complete, and the Streamlit archetype shipped in `create-forge 0.5.0` (its plan
is the [Streamlit Archetype](docs/roadmap-v4/README.md) roadmap). Follow
[open work](https://github.com/Sandsy09/create-forge/issues) and
[releases](https://github.com/Sandsy09/create-forge/releases) for updates, or
suggest a project type, capability, or guide you would find useful.

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
