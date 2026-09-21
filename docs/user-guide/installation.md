# Installation and versions

create-forge supports four install modes. Each resolves the required
`forge-template` engine (`>=0.6,<0.7`) automatically — it is a normal
dependency, not an extra.

## Run without a persistent install

```bash
uvx create-forge new
uvx create-forge@latest new
uvx create-forge@0.5.0 new
```

`uvx` runs a tool in an isolated environment. A plain invocation may reuse
a cached version or the version installed with `uv tool install`.
`@latest` checks for the latest release; `@0.5.0` requests that exact CLI
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
uv tool install "create-forge==0.5.0"
uv tool upgrade create-forge
```

The upgrade respects the original constraint: an exact pin remains pinned.
Replace the constraint to move to the latest release:

```bash
uv tool install create-forge@latest
```

See [uv's tool version rules](https://docs.astral.sh/uv/concepts/tools/)
for cache behaviour, isolation, and upgrading tool dependencies.

## Install into an active environment

```bash
pip install create-forge
create-forge new
```

Works the same as the modes above; `forge-template` and `uv` resolve into
the same environment. Use this when you already manage a virtual
environment yourself rather than through `uv tool` or `uvx`.

## Add the legacy Copier route

Any of the modes above accept the optional `legacy` extra, which adds
`copier` back for `--template`/`--template-url`/`--ref` and updating a
recorded `.copier-answers.yml` project (`new --legacy`, `update`):

```bash
uv tool install "create-forge[legacy]"
# or:
pip install "create-forge[legacy]"
# or, without a persistent install:
uvx --from "create-forge[legacy]" create-forge new --legacy
```

Without the extra, `--legacy` and a Copier-recorded `update` both exit `3`
naming this remedy. `create-forge doctor` reports whether `copier` is
resolved and, if so, at what version.

## CLI versions and template versions are separate

| Selection | Controls |
| --- | --- |
| `create-forge@0.5.0` | The CLI package version used by uvx. |
| `new --engine-source <url> --engine-ref v1.2.3` | An isolated override of the engine itself, provisioned fresh for one run — not part of a normal install. |
| `new --legacy --ref v0.4.1` | The template repository's Git tag on the `--legacy` Copier path. |

Pin the CLI for a repeatable starting point:

```bash
uvx create-forge@0.5.0 new "Pinned Library" --archetype library --yes
```

Pinning the CLI does not freeze dependency resolution; keep the generated
`uv.lock` under version control. `--ref`, `--template`, and
`--template-url` require `--legacy`. Upgrading the tool or engine does not
change files in projects you have already generated — see [project
updates](updates.md), or [migration](migration.md) if you are moving a
`0.3.x` install or project forward.
