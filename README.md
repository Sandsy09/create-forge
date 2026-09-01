# create-forge

[![CI](https://github.com/Sandsy09/create-forge/actions/workflows/ci.yml/badge.svg)](https://github.com/Sandsy09/create-forge/actions/workflows/ci.yml)

Scaffold modern Python projects from maintained templates — and pull template
improvements back into projects you generated months ago.

```bash
uvx create-forge new
```

No install step. Requires [uv](https://docs.astral.sh/uv/) and git.

## Why

Most project generators are fire-and-forget: you scaffold once, and from that
moment your project drifts away from the template. Six months later the template
has better lint rules, a security fix in CI, and a newer toolchain — and no path
to get any of it into projects already in the wild.

create-forge is built on [Copier](https://copier.readthedocs.io/), which does a
three-way merge between the template version your project was generated from and
the latest one. Local edits survive; template changes arrive.

```bash
uvx create-forge update
```

## What you get

Every generated project ships with:

- **[uv](https://docs.astral.sh/uv/)** for packaging and dependency management
- **[Ruff](https://docs.astral.sh/ruff/)** for linting and formatting
- **mypy** or **pyright** (or both) for type checking
- **pytest** with coverage
- **pre-commit** hooks, including Conventional Commits enforcement
- **GitHub Actions** CI, with a test matrix across your supported Python versions
- **Renovate** or **Dependabot** for dependency updates
- `README`, `CONTRIBUTING`, `SECURITY`, `CHANGELOG`, issue and PR templates
- Optionally: a MkDocs documentation site and ADR scaffolding

Choices you make at scaffold time — build backend, versioning strategy, license,
type checker — are remembered, so updates respect them.

## Usage

```bash
# Interactive
uvx create-forge new

# Named up front
uvx create-forge new "Credit Risk Utils"

# Non-interactive, for scripts and CI
uvx create-forge new "My Lib" --yes \
  --data build_backend=hatchling \
  --data versioning=vcs \
  --data type_checking=both

# Validate an update without changing project files
uvx create-forge update --dry-run
```

| Command | What it does |
| --- | --- |
| `new` | Create a project |
| `list` | Show available templates |
| `update` | Pull template changes into an existing project |
| `doctor` | Check your environment can scaffold and update |
| `config` | Inspect or initialise your saved configuration |

Useful flags on `new`: `--template/-t`, `--path/-p`, `--data/-d`, `--yes/-y`,
`--ref`, `--dry-run`.

Useful flags on `update`: `--ref`, `--dry-run`. An update dry run validates the
requested template update but does not apply it or produce a file-by-file diff.

## Configuration

Optional. Saves retyping the same answers:

```toml
# ~/.config/create-forge/config.toml
author_name = "Your Name"
author_email = "you@example.com"
github_org = "your-org"
default_template = "library"
```

`create-forge config init` writes a commented starter file at that path
without overwriting one that already exists. `create-forge config show`
prints the resolved values and where each came from.

`github_org` pre-fills its prompt — you're still asked, just with the answer
already typed in. `author_name` and `author_email` aren't prompted for at all,
so a configured value is applied directly. `default_template` picks which
template `new` offers first, interactively or under `--yes`.

Every key can be overridden with an environment variable —
`FORGE_GITHUB_ORG` and so on — or a command line flag. Precedence is
config < environment < `--data` < an interactive answer.

## Templates

Run `create-forge list` for what your installed version offers. The registry is
bundled with each release, so new templates arrive when you update the tool.

To use your own template:

```bash
uvx create-forge new --template-url https://github.com/you/your-template
```

This describes the released v0.1.x architecture. Forge has accepted a future
[public-engine integration contract](docs/integration-contract.md) in which a
versioned `forge-template` package owns discovery and rendering. Its strict
[ProjectSpec protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md)
and [component manifest protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/component-manifests.md)
are now implemented behind the canonical
[stable template-engine API](https://github.com/Sandsy09/forge-template/blob/main/docs/template-engine-api.md)
([ADR 0029](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0029-stable-template-engine-api.md)).
The canonical
[organisation-policy protocol v1](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
defines how downstream clients resolve component-selection defaults and
constraints before constructing that effective ProjectSpec. CF-09.01
([ADR 0022](docs/adr/0022-downstream-organisation-policy-hook.md)) delivered
the client-side consumption hook — this repository still resolves no policy
itself; see the canonical
[downstream policy-consumption contract](docs/organisation-policy-consumption.md).
The canonical
[safe extension contract](https://github.com/Sandsy09/forge-template/blob/main/docs/extension-points.md),
[organisation-policy fixture](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy-fixtures.md),
[compatibility policy](https://github.com/Sandsy09/forge-template/blob/main/docs/compatibility-policy.md),
and [no-copy proof](https://github.com/Sandsy09/forge-template/blob/main/docs/no-copy-inheritance.md)
complete forge-template's Stage 09 boundary. They deny arbitrary file
replacement and prove that a client can retain policy/orchestration concerns
without copying engine content or importing private engine modules. The
decisions are recorded by forge-template
[ADRs 0039](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0039-deny-policy-file-overrides.md),
[0040](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0040-organisation-policy-reference-fixture.md),
[0041](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0041-forge-blueprint-compatibility-policy.md),
and [0042](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0042-validate-no-copy-downstream-inheritance.md).
The accepted
[Library archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/library-archetype.md)
defines the first production component, implemented on `forge-template/main`
and released at `0.3.0`. The accepted
[CLI Application archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/cli-application-archetype.md)
selects the optionless engine-owned `cli` archetype and derives its console
command from `ProjectSpec.project.repository_name`;
[FT-08.04](https://github.com/Sandsy09/forge-template/issues/4) implemented
it in the same `0.3.0` release, and
[CF-08.02](https://github.com/Sandsy09/create-forge/issues/10) exposes both
archetypes behind the hidden `new --engine-preview` flag's `--archetype`
option. Neither change alters this CLI's default `new` answers, registry, or
released dependency surface.
The Stage 08
[composition architecture review](https://github.com/Sandsy09/forge-template/blob/main/docs/composition-architecture-review.md)
is released in `forge-template 0.3.2`. On the engine-preview path,
`create-forge 0.2.1` now finalises the validated in-memory render with
`uv lock --directory <staging-directory>` before the atomic rename. The
result contains `uv.lock` and uses `uv run --locked poe check`, while the
default Copier path remains unchanged; see
[ADR 0021](docs/adr/0021-client-finalises-engine-lockfiles.md).
The engine now also defines in-memory
[generated-project validation](https://github.com/Sandsy09/forge-template/blob/main/docs/generated-project-validation.md)
([ADR 0030](https://github.com/Sandsy09/forge-template/blob/main/docs/adr/0030-generated-project-validation.md))
before rendered output is returned; `render_project` already calls it before
`--engine-preview` receives a result.
This repository now depends on a real, released `forge-template` range —
`>=0.3.1,<0.4`, published to PyPI with `uv>=0.12,<0.13` as the optional
`engine` extra
(`pip install 'create-forge[engine]'`; [#9](https://github.com/Sandsy09/create-forge/issues/9),
[ADR 0018](docs/adr/0018-pypi-distribution-and-the-first-engine-range.md)) —
rather than a development-only pin. That range is reachable only behind
`--engine-preview`; the current registry and `--template-url` behaviour
remain unchanged until the complete, tested cutover is released — at which
point `--engine-source`/`--engine-ref` (see the
[engine resolution contract](docs/engine-resolution.md)) take over this role,
not `--template-url`.

## Security

**create-forge executes code from the template it clones.** Copier templates can
declare post-generation tasks, and this tool runs them — that is how a generated
project arrives already git-initialised with hooks installed.

The template addresses are compiled into each release rather than fetched at
runtime or read from user configuration, so the only code trusted by default is
code published alongside the tool. `--template-url` bypasses that, and prompts
for confirmation before doing so. Point it only at repositories you trust.

Report vulnerabilities per [SECURITY.md](SECURITY.md) rather than in a public
issue.

## Using this at work

The preferred route for organisation defaults, required selections, and
forbidden selections is a downstream client of the public `forge-template`
engine, resolving the canonical
[organisation-policy protocol](https://github.com/Sandsy09/forge-template/blob/main/docs/organisation-policy.md)
before constructing a ProjectSpec — see the canonical
[downstream policy-consumption contract](docs/organisation-policy-consumption.md)
and [ADR 0022](docs/adr/0022-downstream-organisation-policy-hook.md).
[`examples/downstream_cli.py`](examples/downstream_cli.py) is a runnable,
second, independent client demonstrating exactly this — no dependency on
`create-forge` at all — see the canonical
[downstream client reference](docs/downstream-client-reference.md) and
[ADR 0023](docs/adr/0023-downstream-client-reference.md).
[ADR 0024](docs/adr/0024-reference-client-not-framework-dependency.md)
completes the Stage 09 boundary: `create-forge` is one reference client, not a
framework dependency for that client, the engine, or generated projects.

Forking this repository remains appropriate only for genuinely custom
executable template content that has no equivalent in the reviewed public
engine — point the bundled registry at your own templates and maintain the
fork internally, as v0.1.x always supported. See the
[integration contract](docs/integration-contract.md) for the full boundary.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and pull requests welcome.
Significant design decisions are recorded in [docs/adr/](docs/adr/).

## License

MIT — see [LICENSE](LICENSE).
