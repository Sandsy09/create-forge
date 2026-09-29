# CLI command map

This is the behavioural baseline [CF-25.01](https://github.com/Sandsy09/create-forge/issues/201)
recorded before [CF-25.02](https://github.com/Sandsy09/create-forge/issues/202)
moved any code — every command's inputs, prompts, outputs, and config
effects. [CF-25.02](https://github.com/Sandsy09/create-forge/issues/202) has
since completed the `commands/` extraction it describes, reproducing every
behaviour recorded here exactly; the "Lazy import call sites" section below
is kept current to name each function's actual post-extraction home. It is a
companion to two other documents, not a replacement for either:

- [`cli-conventions.md`](cli-conventions.md) stays the authoritative source
  for *why* — prompt-skipping rules, interactive/non-interactive parity,
  validation ownership, and the one exit-status table. This document
  cross-references it rather than restating it.
- [ADR 0060](adr/0060-cli-command-module-seams.md) is the *architecture*
  decision — the `commands/` subpackage layout, dependency direction, and
  the approved extraction sequence this document's behaviour baseline held
  through.

## The one public entry point

```toml
[project.scripts]
create-forge = "create_forge.cli:app"
```

This is the only way `create-forge` is invoked — `uvx`, `uv tool install`,
`pip install`, and the `legacy` extra all resolve this one script.
**`python -m create_forge` is not a supported entry point**: `src/
create_forge/__main__.py` does not exist, and CF-25.01 deliberately did not
add one — pinned by `tests/test_engine_contract.py::
test_the_one_public_console_script_entry_point_is_unchanged`. This line is
unmoved by CF-25.02: `cli.py` keeps the `app` object regardless of where each
command's own orchestration lives (ADR 0060 decision 2).

## Lazy import call sites

Post-CF-25.02 (verified against the current source, not assumed): `cli.py`
itself has no module-scope import of `runner`/`pipeline`/`engine`/
`engine_source`/`update` at all — it imports only `typer`, `commands/*`, and
`create_forge.sources`. Every lazy import moved with its function, into
whichever `commands/*` module now holds it — the shape [ADR
0014](adr/0014-lazy-engine-reachability.md) established, extended to
`commands/*` by [ADR 0060](adr/0060-cli-command-module-seams.md):

- `commands/_legacy.py`: `_ensure_legacy_available` (`import
  create_forge.runner`).
- `commands/new.py`: `new`'s legacy branch (`from create_forge.runner import
  ScaffoldRequest`), `_run_scaffold` (`from create_forge.runner import
  ScaffoldError, scaffold`), `_run_engine` (`from create_forge import engine,
  pipeline`), `_run_engine_source` (`from create_forge import engine_source,
  pipeline`).
- `commands/catalogue.py`: `list_templates` (`from create_forge import
  engine, pipeline`).
- `commands/update.py`: `update_project` (`from create_forge import engine,
  update`), `_run_copier_update` (`from create_forge.update import
  COPIER_ANSWERS_FILE`; `from create_forge.runner import ScaffoldError`; `from
  create_forge.runner import update as copier_update`), `_run_engine_update`
  (`from create_forge import engine, pipeline, update`), `_print_recovery`
  (`from create_forge import update`).
- `commands/doctor.py`: `_tooling_diagnostics` (`from create_forge.runner
  import cache_probe, copier_cache_location`), `_gather_diagnostics` (`from
  create_forge import engine as _engine`).

## `new`

| | |
| --- | --- |
| **Inputs** | Positional `NAME`; `--template`/`-t`, `--path`/`-p`, `--data`/`-d` (repeatable), `--yes`/`-y`, `--template-url`, `--ref`, `--dry-run`, `--legacy` (Copier-route flags); `--archetype`, `--capability` (repeatable), `--no-capabilities`, `--platform` (repeatable), `--no-platforms`, `--component-option` (repeatable) (engine-route flags); `--engine-source`, `--engine-ref` (isolated-engine override). Plus the loaded config file and matching `FORGE_*` environment overrides. |
| **Prompts** | Legacy route: template choice (skipped by `--template`, a single selectable template, or `--yes`), then `ask_all`'s registry-driven questions. Engine/engine-source routes: archetype choice (skipped by `--archetype` or, with `--yes`, rejected outright), capability/platform multi-selects per kind (skipped when the flag was given, the kind has no discovered descriptors, or every descriptor of it is required), then `ask_project_answers` (`project_name`/`project_description`/`license`) and `resolve_component_options` (per selected component's own declared options). `--template-url`/`--engine-source` print a code-execution warning unconditionally and ask for confirmation unless `--yes`. |
| **Outputs** | Success: one green `Panel` (`_report_created`) naming the project, its destination, the `cd` line, the check command, and an update-eligibility line (three distinct wordings: updatable, engine-source "not eligible", or plain "not yet eligible"). `--dry-run`: `would write <target>` per planned file, then `Dry run — nothing written.`. Failure: a single red-styled line to stderr, never a raw traceback. |
| **Exit codes** | `0` success, `--dry-run`, `--help`. `1`: unknown template/archetype/component id, contradictory flags, malformed config, non-empty destination, staging/lock failure, scaffold/render failure, an unselected `--component-option` owner. `2`: malformed `--data`/`--component-option`, unrecognised option (Typer). `3`: engine missing or incompatible, `--legacy` without the extra installed, `--engine-source`'s provisioned engine incompatible. `130`: any prompt cancelled, `--template-url`/`--engine-source` confirmation declined, Ctrl-C mid-render (both routes verified clean via `staging.staged`'s and `staging.discard_on_failure`'s `except BaseException`). |
| **Config effects** | `default_template` (legacy route only); `author_name`/`author_email`/`github_org` pre-fill answers on both routes (`cfg_answers`), overridable by prompt or `--data`/`--component-option`. |

## `list`

| | |
| --- | --- |
| **Inputs** | `--legacy` (prints the bundled Copier registry table instead of the discovered engine catalogue). |
| **Prompts** | None. |
| **Outputs** | A table: `ID`/`Name`/`Description`/`Status` (`--legacy`) or `ID`/`Kind`/`Name`/`Description` (default, grouped archetypes-then-capabilities-then-platforms). |
| **Exit codes** | `0` normal. `1`: `--legacy` with a malformed bundled registry (CF-25.01 found and fixed this — see below) or a `ForgeEngineError` from discovery. `3`: engine missing or incompatible (default route). |
| **Config effects** | None. |

**Real defect found and fixed while characterising this command (CF-25.01):**
`_list_legacy_registry` called `load_registry()` with no error handling, so a
malformed bundled registry crashed with a raw traceback instead of the clean
exit-`1` message every other reader of the registry (`doctor`,
`_select_template`) already produces — the one inconsistency in CLAUDE.md's
"no traceback reaches the user" convention. Fixed with the same
`try/except RuntimeError` shape those callers use.
`tests/test_cli.py::test_list_legacy_broken_registry_is_a_user_error` is the
regression test, proven red against the unfixed code first.

## `update`

| | |
| --- | --- |
| **Inputs** | Positional `PROJECT` (default: cwd); `--ref` (Copier route only), `--dry-run`, `--legacy`, `--degraded` (engine-native route only). |
| **Prompts** | Interactive degraded-fallback confirmation (`_confirm_degraded`) when the engine-native route's recorded release is unavailable and `--degraded` was not passed; declining, or a closed stdin hitting EOF (verified real, not just mocked — `test_engine_update_unavailable_release_closed_stdin_declines_for_real`), both behave as a decline. |
| **Outputs** | Engine-native `--dry-run`: a per-target classification list plus an unchanged-target count, then `Dry run complete. No project files changed.`. Engine-native real run: `Updated.` plus a clean/conflicted count, or `Nothing changed.` for a no-op. Copier route: unchanged pre-cutover wording. Failure/cancellation: recovery guidance printed from the repository's *actual* Git state (`_print_recovery`), never a canned command, and never printed before the clean-tree precondition passes. |
| **Exit codes** | `0`. `1`: dirty tree, bad merge, missing metadata, no route, staging/merge failure, `--ref` on the engine-native route, `--degraded` on the Copier route. `3`: incompatible/unavailable engine, a declined (or closed-stdin) degraded fallback. `130`: Ctrl-C, verified via `test_engine_update_keyboard_interrupt_exits_130_and_reports_the_real_state`. |
| **Config effects** | None — routing reads only the project's own recorded files. |

## `doctor`

| | |
| --- | --- |
| **Inputs** | `--json`. |
| **Prompts** | None; stays offline (no network call). |
| **Outputs** | A Rich table or (with `--json`) the documented JSON shape ([`engine-resolution.md`](engine-resolution.md)'s diagnostics contract) — the two forms report identical facts. |
| **Exit codes** | `0` every check passes. `1` any non-informational check fails. |
| **Config effects** | Reports where config was read from and which keys it set; does not itself consume config to change behaviour. |

## `config init`

| | |
| --- | --- |
| **Inputs** | None. |
| **Outputs** | Writes a commented starter file at `config_path()`, or prints "already exists — left untouched" without overwriting. |
| **Exit codes** | `0` always. |

## `config show`

| | |
| --- | --- |
| **Inputs** | None. |
| **Outputs** | A table of every config field, its resolved value, and its source (`config file`/`environment`/`unset`). |
| **Exit codes** | `0` normal. `1` malformed config TOML (`test_config_show_malformed_config_is_a_user_error`, CF-25.01). |

## `--help` and usage

Every command's `--help` exits `0` (`test_help_exits_zero`, parametrised over
the top-level app and all seven subcommands/sub-subcommands). Invoking
`create-forge` with no arguments exits `2` (Typer's `no_args_is_help=True`
still prints help, but a bare invocation is a usage non-answer, not success —
`test_no_args_is_help_and_exits_2`). `new`'s and `update`'s full flag
surfaces are checked (`test_new_registers_every_route_and_selection_flag`,
`test_update_registers_its_flags`) against the live Click command object,
not `--help`'s *rendered* text — CF-25.01 found that a text-scraping version
of these two passed locally but failed on every CI runner with a flag
missing from the rendered output despite exit `0` and no exception, an
unexplained Rich-rendering divergence a much wider forced `COLUMNS` did not
fix. Reading the command object instead sidesteps it entirely and is the
same approach `test_engine_default_contract.py`/
`test_engine_lifecycle_contract.py` already use for their own flag-presence
checks. Either shape still fails when a file move breaks a command's
registration in `commands/*`.

## Executable examples

The full test-name-to-behaviour map lives in
[`cli-conventions.md`](cli-conventions.md#executable-examples); this
document's own additions from CF-25.01 are named inline above. See also
`tests/test_engine_default_contract.py` and
`tests/test_engine_lifecycle_contract.py` for the derived, live-CLI
assertions (flag visibility, the parameter set, the exit-status table's own
wording) that do not belong to one single command.
