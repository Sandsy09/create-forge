# Build a Python project with Forge

Forge gives you a working project structure, dependency management, and
quality checks so you can start writing your own code.

`create-forge` is the command-line tool. Its companion, `forge-template`,
provides the generated content and the optional composition engine. You do
not need to clone either repository to generate a project, and your
generated application does not depend on Forge at runtime.

This guide covers **create-forge 0.3.0** and **forge-template 0.4.1**. The
default workflow creates an updatable Library project. CLI Application,
Data Science, and reusable capabilities are available through the
[engine preview](projects.md).

## Before you start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[Git](https://git-scm.com/downloads). Forge requires Python 3.11 or newer;
uv can download a suitable Python interpreter when needed.

Check your environment:

```bash
uvx create-forge doctor
git config user.name
git config user.email
```

The default template creates a local Git repository and commits its
initial files. If either Git setting is missing, configure the identity
you want to use for your projects before continuing:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

First-time generation needs network access to retrieve the template and
resolve project dependencies. Choose a new or empty destination directory.

## Your first project

```bash
uvx create-forge new "My Library"
cd my-library
uv run poe check
```

Answer the prompts for your project, packaging, and tooling choices. The
command creates `my-library/`, installs development dependencies, and sets
up Git hooks. `poe check` runs the generated project's formatter check,
linter, type checker, and tests.

Open `src/my_library/` to add package code and `tests/` to test it. Read the
generated README for that project's tasks and contribution workflow.

## Choose your next step

- [Install the tool or pin versions](installation.md).
- [Choose a project type](projects.md), then follow a Library, CLI, or
  Data Science recipe.
- [Automate generation and save answers](cli.md).
- [Update your project or diagnose a problem](updates.md).
- [Suggest a guide or report a problem](feedback.md).

Commands use single lines so they can be copied into PowerShell or a POSIX
shell. Run each recipe from a parent directory with room for a new project.
