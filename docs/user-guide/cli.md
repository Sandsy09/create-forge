# CLI usage

## Commands

| Command | Purpose |
| --- | --- |
| `new [NAME]` | Generate a project through the engine (default) or `--legacy` Copier; ask for missing answers interactively. |
| `list` | List the discovered engine catalogue (default), or `list --legacy` for the bundled Copier template registry. |
| `update [PROJECT]` | Update a project, defaulting to the current directory. Routes automatically by the project's own files; `--legacy` forces the Copier route. |
| `doctor` | Report environment and package compatibility checks. |
| `config init` | Write a commented starter configuration without overwriting an existing file. |
| `config show` | Display effective configuration and each value's source. |

Prefix these with `uvx create-forge` or use the installed `create-forge`
command. `--help` and `new --help` describe the full public workflow —
nothing is hidden.

## Name, destination, and selection

```bash
uvx create-forge new "Credit Risk Utils" --archetype library --path credit-risk-utils --data license=mit
```

The name becomes the default repository slug and import-package name.
`--path` controls where files are written. An existing non-empty directory
is rejected; choose a new or empty one.

`--archetype` selects the project type (`library`, `cli`, `data-science`, …
— run `create-forge list` for the discovered catalogue); `--capability`
(repeatable) and `--platform` add optional tooling. Repeat `--data
key=value` for prompt presets. A preset skips that question; other
questions remain interactive. See [component
selection](https://github.com/Sandsy09/create-forge/blob/main/docs/component-selection.md)
for precedence and prompt order, and [choosing a project
type](projects.md) for a recipe per archetype.

## Scripts and CI

```bash
uvx create-forge@0.4.0 new "Automation Lib" --archetype library --yes --data author_name=Example --data author_email=example@example.com
```

`--yes` requires `--archetype`, skips questions, and uses defaults for
unspecified answers. In CI, also supply Git's committer identity before
running `new`: `author_name` and `author_email` are generated project
metadata and do not configure Git itself. Generation resolves the engine
and creates a lockfile, then runs `git init`, an initial commit, and
(if selected) installs pre-commit hooks.

Use `new --dry-run` to inspect generation without writing a project. A
successful dry run does not prove the generated project's dependency
installation or checks will succeed.

## Save common answers

```bash
uvx create-forge config init
uvx create-forge config show
```

Edit `~/.config/create-forge/config.toml`, or
`$XDG_CONFIG_HOME/create-forge/config.toml` when that environment variable
is set. This location is also used on Windows.

```toml
author_name = "Your Name"
author_email = "you@example.com"
github_org = "your-org"
default_template = "library"
```

Environment variables such as `FORGE_AUTHOR_NAME`, `FORGE_AUTHOR_EMAIL`,
`FORGE_GITHUB_ORG`, and `FORGE_DEFAULT_TEMPLATE` override file values.
Explicit command options and `--data` take precedence over those defaults.
Interactive questions prefilled from configuration can still be changed.

`github_org` and `default_template` apply to the `--legacy` Copier path;
the engine path selects its archetype independently and does not use the
GitHub organisation answer. Configured author details apply to both paths.

## Use a Copier template (`--legacy`)

```bash
uvx create-forge new "Custom Project" --legacy --template-url https://github.com/you/your-template
```

`--legacy` and any of `--template`, `--template-url`, or `--ref` require
the `legacy` extra (`create-forge[legacy]` — see
[installation](installation.md)); without it, the command exits `3` naming
the remedy. Replace the URL with a Copier template you trust — it may
execute arbitrary generation or update tasks. The command warns and asks
for confirmation; `--yes` skips that confirmation as well as normal
questions.

Template URLs must be credential-free: HTTP(S) usernames, passwords or
tokens in the URL are rejected, as are SSH URL passwords and URL queries or
fragments. Authenticate with an external Git credential helper or SSH
agent. An SSH username such as `git` in
`git@github.com:you/your-template.git` is supported. Use `--ref` for a tag
or branch instead of a URL fragment. These checks also apply with `--yes`
and `--dry-run`, and to Copier's `git+`, `gh:` and `gl:` source forms.

When updating an existing `--legacy`-generated project, the recorded
`_src_path` in `.copier-answers.yml` must follow the same policy. If it
contains credentials, replace it with the equivalent credential-free source
and configure external authentication before retrying. The CLI reports the
affected field without printing its value and does not edit the answers
file for you.

The CLI's interactive questions for the bundled template still come from
its own registry. For a custom template with different questions, pass
matching `--data` answers with `--yes`, or use Copier directly for its
native prompt flow. Unknown Copier answer keys can be ignored, so consult
that template's schema rather than guessing names.

To try a trusted local Git checkout, use its path and `--ref HEAD`:

```bash
uvx create-forge new "Local Template Trial" --legacy --template-url ../your-template --ref HEAD
```

Under Copier 9, `HEAD` includes the checkout's working-tree changes.
Omitting it selects the latest release tag instead.
