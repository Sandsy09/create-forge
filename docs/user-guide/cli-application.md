# Build a CLI application

Use the CLI Application preview for a Python tool people run from their
terminal. It generates a Typer application with a console entry point,
a `python -m` entry point, and tests for the starter command.

## Generate and run

```bash
uvx --from "create-forge[engine]==0.3.2" create-forge new "Weather Tools" --engine-preview --archetype cli --yes --data license=mit
cd weather-tools
uv run --locked poe check
uv run weather-tools --help
uv run weather-tools hello Ada
uv run python -m weather_tools hello Ada
```

Both `hello` invocations print `Hello, Ada!`. The repository name determines
the console command (`weather-tools`); the package name determines the
module (`weather_tools`). `uv run weather-tools --version` prints the
installed project version.

## Make it your own

Add commands to `src/weather_tools/cli.py` and test them in
`tests/test_cli.py`. Keep reusable application logic in other package
modules, then call it from the command handlers.

```bash
uv run --locked poe check
uv build
```

The build produces distribution files under `dist/`. This archetype uses
fixed packaging and currently has no component options. It includes the
[shared preview tooling](projects.md#what-preview-projects-share), but does
not initialise Git or create CI workflows.

You can add [Jupyter or Scientific Python](capabilities.md) at generation
time, for example when the command wraps a numerical analysis. Generated
preview projects do not support `create-forge update`.
