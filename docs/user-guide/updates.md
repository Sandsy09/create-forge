# Updates and troubleshooting

## Update a Copier-generated project

Tool upgrades and project updates are separate operations. `uv tool upgrade`
changes your installed CLI; `create-forge update` brings template changes
into an existing Copier-generated project.

Start with a clean, committed Git working tree and keep the project's
`.copier-answers.yml` tracked. From its root:

```bash
uvx create-forge update --dry-run
uvx create-forge update
git diff
uv run poe check
```

Review changes and resolve conflicts before committing. Copier merges
template changes with local edits, but a clean merge is not guaranteed.
In particular, competing additions at the very end of a templated file can
lose local text; review those sections carefully and use your committed
history to restore it when needed.

A dry run validates the requested update without changing project files.
It does not show a file-by-file diff or prove all post-update checks pass.

### Choose a target release

```bash
uvx create-forge update --ref v0.4.1
```

The ref belongs to the recorded template repository. Without it, Copier
selects the latest suitable release tag. To update a project elsewhere,
pass its directory: `uvx create-forge update path/to/project`.

Direct Copier users can run `uvx copier update --trust` from the project
root. Only trust templates whose update tasks you are willing to execute.

## Preview projects

Engine-preview projects do not contain Copier update metadata and cannot
use `create-forge update`. Upgrading the engine affects future generations
only. Maintain an existing preview project as ordinary Python source, or
generate a separate project to compare a newer scaffold manually. There is
currently no automated migration between the two workflows.

## Diagnose problems

```bash
uvx create-forge --version
uvx create-forge doctor
uvx create-forge doctor --json
```

For the pinned preview environment instead:

```bash
uvx --from "create-forge[engine]==0.3.0" create-forge doctor
```

| Symptom | Next step |
| --- | --- |
| Installed command is missing | Run `uv tool update-shell`, then open a new terminal. |
| uvx runs an older CLI | Request `create-forge@latest`, or update your persistent installation. |
| Generation cannot commit | Check `git config user.name` and `git config user.email`. |
| Template download fails | Check the repository URL, requested Git ref, network, and repository access. |
| Template cache is unusable, or `doctor` reports it not writable | Point `COPIER_CACHE_DIR` at a fresh writable directory (see below). Common on managed machines. |
| Destination already contains files | Choose a new or empty directory; generation does not overwrite a populated project. |
| Engine is missing or incompatible | Install the engine extra and run diagnostics in that same environment. |
| Data Science rejects the selection | Include `--capability jupyter`; an explicit scientific stack alone is insufficient. |
| Preview reports `project.licence: Field required` | Supply `--data license=mit`, `proprietary`, or `apache-2.0` with `--yes`. |
| Preview rejects `--ref` | Select the engine package version through uv; `--ref` is for Copier. |
| Notebook checks fail | Read the reported file/error, clear stored outputs and counts, and inspect notebook code before rerunning. |
| A generated check fails | Run the named task from the generated project and include its output in a template bug report. |

Before retrying a failed generation, inspect the destination. Report the
exact command, CLI version, template tag or engine version, operating
system, and relevant error output through [feedback](feedback.md). Remove
credentials and private data from commands and logs before posting.

## Redirect the template cache

Copier keeps a git mirror of each template under a per-user cache directory.
On a managed or corporate machine that location can be redirected to a path
that is missing, read-only, or not a real Git repository, and generation then
fails with a cache error. `create-forge doctor` shows the resolved cache path
and whether it is writable.

Point Copier at a fresh, writable directory — do not delete the existing one:

```powershell
$env:COPIER_CACHE_DIR = "C:\forge-cache"
```

```bash
export COPIER_CACHE_DIR="$HOME/.cache/forge-copier"
```

Then re-run `create-forge doctor` in the same shell to confirm the new path is
writable, and retry generation. To make it permanent, set `COPIER_CACHE_DIR`
in your shell profile or system environment.

Capture `create-forge doctor --json` *before* retrying a failed generation:
Copier removes its temporary worktree when a run fails, so diagnostics
collected afterwards no longer show the state that caused it.
