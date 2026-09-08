# CLI usage

## Commands

| Command | Purpose |
| --- | --- |
| `new [NAME]` | Generate a project; ask for missing answers interactively. |
| `list` | List the bundled Copier template registry, currently Library. |
| `update [PROJECT]` | Update a Copier-generated project, defaulting to the current directory. |
| `doctor` | Report environment and package compatibility checks. |
| `config init` | Write a commented starter configuration without overwriting an existing file. |
| `config show` | Display effective configuration and each value's source. |

Prefix these with `uvx create-forge` or use the installed `create-forge`
command. `--help` and `new --help` describe the default public workflow;
the [preview options](capabilities.md) are currently hidden from help.

## Name, destination, and answers

```bash
uvx create-forge new "Credit Risk Utils" --path credit-risk-utils --data license=mit
```

The name becomes the default repository slug and import-package name.
`--path` controls where files are written. An existing non-empty directory
is rejected; choose a new or empty one.

Repeat `--data key=value` for more presets. A preset skips that question;
other questions remain interactive. The default template's
[question schema](https://github.com/Sandsy09/forge-template/blob/v0.4.1/copier.yml)
lists all supported answers, including ones the CLI does not prompt for.

## Scripts and CI

```bash
uvx create-forge@0.3.2 new "Automation Lib" --ref v0.4.1 --yes --data github_org=example-org --data author_name=Example --data author_email=example@example.com --data build_backend=hatchling --data versioning=static
```

`--yes` requires a project name, skips questions, and uses defaults for
unspecified answers. In CI, also supply Git's committer identity before
running the default template: `author_name` and `author_email` are generated
project metadata and do not configure Git itself. Generation may download
dependencies and run template tasks.

Use `new --dry-run` to inspect generation without writing a project. It
can still require network access. A successful dry run does not prove the
generated project's dependency installation or checks will succeed.

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

The default workflow uses `github_org` and `default_template`; preview
archetypes are selected independently, and the engine does not use the
GitHub organisation answer. Configured author details apply to both paths.

## Use another Copier template

```bash
uvx create-forge new "Custom Project" --template-url https://github.com/you/your-template
```

Replace the URL with a Copier template you trust. It may execute arbitrary
generation or update tasks. The command warns and asks for confirmation;
`--yes` skips that confirmation as well as normal questions.

Source validation is enforced by released `0.3.2`. Use credential-free
sources with every version.

Template URLs must be credential-free: HTTP(S) usernames, passwords or tokens
in the URL are rejected, as are SSH URL passwords and URL queries or
fragments. Authenticate with an external Git credential helper or SSH agent.
An SSH username such as `git` in `git@github.com:you/your-template.git` is
supported. Use `--ref` for a tag or branch instead of a URL fragment.
These checks also apply with `--yes` and `--dry-run`, and to Copier's
`git+`, `gh:` and `gl:` source forms.

When updating an existing project, the recorded `_src_path` in
`.copier-answers.yml` must follow the same policy. If it contains credentials,
replace it with the equivalent credential-free source and configure external
authentication before retrying. The CLI reports the affected field without
printing its value and does not edit the answers file for you.

The CLI's interactive questions still come from its bundled template
registry. For a custom template with different questions, pass matching
`--data` answers with `--yes`, or use Copier directly for its native prompt
flow. Unknown Copier answer keys can be ignored, so consult that template's
schema rather than guessing names.

To try a trusted local Git checkout, use its path and `--ref HEAD`:

```bash
uvx create-forge new "Local Template Trial" --template-url ../your-template --ref HEAD
```

Under Copier 9, `HEAD` includes the checkout's working-tree changes.
Omitting it selects the latest release tag instead.
