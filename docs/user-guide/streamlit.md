# Start a Streamlit project

Use the `streamlit` archetype for an interactive [Streamlit](https://streamlit.io)
application that is also an installable Python package. It creates a package,
an application entry point, tests, and a locked environment with the same
checks as every other archetype.

## Start an application

```bash
uvx create-forge new "Sales Explorer" --archetype streamlit --yes --data license=mit
cd sales-explorer
uv run --locked poe check
uv run poe run
```

`poe check` runs the generated project's quality checks, including a short test
that renders the starter page without starting a server. The final command
starts the Streamlit server; open the address it prints, and stop it with
Ctrl+C when finished. Starting the server is a separate task, kept out of
`poe check`, because a server never exits and would stop the checks (and your
CI) from finishing.

The generated project's structure, its dependency bounds, and how the `run` and
`check` tasks are defined belong to the template engine. They are documented
in the [Streamlit archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-archetype.md)
rather than repeated here, so this guide cannot drift from what is generated.

## Add the scientific stack

For numerical work, data frames, or charts, select the Scientific Python
capability:

```bash
uvx create-forge new "Model Explorer" --archetype streamlit --capability scientific-python --yes --data license=mit
cd model-explorer
uv run --locked poe check
uv run poe run
```

Jupyter can be added the same way with `--capability jupyter`, and both
capabilities can be combined. See [capabilities](capabilities.md) for what each
one adds.

## Keep secrets out of version control

Streamlit reads secrets from its own secret file, which the generated project
already excludes from Git. How that and the generated configuration work is
defined in the archetype contract's
[configuration and secret safeguards](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-archetype.md#configuration-and-secret-safeguards).
Keep credentials, datasets, and generated binaries out of version control.

## What is not generated

No hosting, container, authentication, or database setup is generated, and
there is no FastAPI surface. The archetype contract lists these
[explicit exclusions](https://github.com/Sandsy09/forge-template/blob/main/docs/streamlit-archetype.md#explicit-exclusions).
Deploy the application with whatever platform you already use.

If a command fails, [updates and troubleshooting](updates.md) explains how to
diagnose the installation with `create-forge doctor`.
