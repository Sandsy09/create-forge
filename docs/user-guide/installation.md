# Installation and versions

## Run without a persistent install

```bash
uvx create-forge new
uvx create-forge@latest new
uvx create-forge@0.3.0 new
```

`uvx` runs a tool in an isolated environment. A plain invocation may reuse
a cached version or the version installed with `uv tool install`.
`@latest` checks for the latest release; `@0.3.0` requests that exact CLI
version. These commands do not add Forge to your project's dependencies.

## Install a command for regular use

```bash
uv tool install create-forge
create-forge --version
create-forge new
uv tool upgrade create-forge
```

If `create-forge` is not found after installation, run
`uv tool update-shell`, then restart your terminal. `uv tool list` shows
installed tools, and `uv tool uninstall create-forge` removes this one.

### Pin or change the installed version

```bash
uv tool install "create-forge==0.3.0"
uv tool upgrade create-forge
```

The upgrade respects the original constraint: an exact pin remains pinned.
Replace the constraint to move to the latest release:

```bash
uv tool install create-forge@latest
```

See [uv's tool version rules](https://docs.astral.sh/uv/concepts/tools/)
for cache behaviour, isolation, and upgrading tool dependencies.

## Install the engine preview

The engine extra installs the compatible `forge-template` package and the
uv version used to finish preview projects' lockfiles:

```bash
uvx --from "create-forge[engine]==0.3.0" create-forge new --engine-preview
```

For a persistent command:

```bash
uv tool install "create-forge[engine]"
create-forge new --engine-preview
uv tool upgrade create-forge
```

Include `[engine]` when replacing an installation constraint if you want
to retain preview support. The `0.3.0` CLI accepts
`forge-template>=0.4.1,<0.5`; this guide's examples are checked with `0.4.1`.
To request that exact engine as well:

```bash
uvx --with "forge-template==0.4.1" --from "create-forge[engine]==0.3.0" create-forge new --engine-preview
```

`create-forge doctor` reports the installed engine and compatible range.
Run diagnostics through the same installation or `uvx --from` command as
generation so you inspect the environment you actually use.

## CLI versions and template versions are separate

| Selection | Controls |
| --- | --- |
| `create-forge@0.3.0` | The CLI package version used by uvx. |
| `new --ref v0.4.1` | The template repository's Git tag on the Copier path. |
| `--with "forge-template==0.4.1"` | The engine package used by a preview invocation. |

Pin both CLI and Copier template for a repeatable starting point:

```bash
uvx create-forge@0.3.0 new "Pinned Library" --template library --ref v0.4.1
```

Without `--ref`, Copier selects the latest suitable release tag. Pinning
the CLI alone does not pin the template, and these pins do not freeze
dependency resolution; keep the generated `uv.lock` under version control.

`--ref`, `--template`, and `--template-url` cannot be used with
`--engine-preview`. Upgrading the tool or engine does not change files in
projects you have already generated. See [project updates](updates.md).
