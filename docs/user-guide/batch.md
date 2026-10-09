# Start a batch project

Use the `batch` archetype for a scheduling-neutral batch job that is also an
installable Python package. It creates a package, a job entry point, tests, a
tracked sample input, and a locked environment with the same checks as every
other archetype.

## Start a job

```bash
uvx create-forge new "Nightly Report" --archetype batch --yes --data license=mit
cd nightly-report
uv run --locked poe check
uv run poe run
```

`poe check` runs the generated project's quality checks, including a short test
that runs the job against its sample input. `poe run` runs the job itself: it
reads the tracked sample input, transforms each record, and writes
`data/output.json`. Unlike a server, the job finishes, so you can run it as
often as you like. The output is regenerated on every run and is not committed.

The generated project's structure, how the job reads and writes its data, and
how it behaves when it is rerun or meets a bad record belong to the template
engine. They are documented in the
[batch archetype contract](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-archetype.md)
rather than repeated here, so this guide cannot drift from what is generated.
The part worth knowing up front is how
[rerunning and failures](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-archetype.md#rerun-idempotency-and-failure-handling)
are handled.

## Add the scientific stack

For numerical work, select the Scientific Python capability:

```bash
uvx create-forge new "Daily Metrics" --archetype batch --capability scientific-python --yes --data license=mit
cd daily-metrics
uv run --locked poe check
uv run poe run
```

Jupyter can be added the same way with `--capability jupyter`, and both
capabilities can be combined. See [capabilities](capabilities.md) for what each
one adds.

## Running it on a schedule

The project does not include a scheduler, queue, worker, or retry logic, so it
works with whichever one you already use: point that tool at the project's
console script, which is named after the project (`nightly-report` in the
example above). The archetype contract lists these
[explicit exclusions](https://github.com/Sandsy09/forge-template/blob/main/docs/batch-archetype.md#explicit-exclusions).

## Make it your own

Edit `src/<package_name>/job.py` to change what the job does, and replace the
sample input with your own data. Later template changes can be pulled in with
`create-forge update`; see [updates and troubleshooting](updates.md).

If a command fails, [updates and troubleshooting](updates.md) also explains how
to diagnose the installation with `create-forge doctor`.
