# 60. Split `cli.py` behind a `commands/` subpackage, along command seams

## Status

Accepted

## Context

[CF-25.01](https://github.com/Sandsy09/create-forge/issues/201), the first
child of [CF-EPIC-25](https://github.com/Sandsy09/create-forge/issues/191),
reports that `src/create_forge/cli.py` (2,149 lines) and `tests/test_cli.py`
(2,490 lines, 80 tests) have grown into one module each, covering five
command groups — `new`, `list`, `update`, `doctor`, `config` — which makes a
command-scoped change hard to review. The epic's stated outcome is to
"reduce command-module coupling while preserving the public CLI and isolation
boundaries"; this issue's own acceptance criteria ask it to "approve a
bounded extraction sequence" without moving any code itself — extraction is
[CF-25.02](https://github.com/Sandsy09/create-forge/issues/202)'s job, test
reorganisation [CF-25.03](https://github.com/Sandsy09/create-forge/issues/203)'s.

`cli.py` today holds, in one file: console/encoding hardening
(`_harden_console_encoding`, `_markers`); shared option-string parsing
(`_parse_data`, `_parse_component_options`); the whole of `new` (legacy,
default-engine, and `--engine-source` orchestration, plus every
archetype/capability/platform/option-selection helper — the majority of the
file); `list`; `update` (file-based routing, the direct-Copier route, the
engine-native route, and Git-state recovery printing); `doctor` (five frozen
dataclasses, diagnostics gathering, table/`--json` rendering); and `config
init`/`config show`.

Two invariants this decision must not touch, both load-bearing today:

- **ADR 0013**/**ADR 0044**: `engine.py` (in process) and `_engine_worker.py`
  (out of process, inside a provisioned `--engine-source` environment) are
  the *only* modules whose source imports `forge_template`. `tests/
  test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`
  enforces this by walking every other production module's imports; CF-25.01
  changed it to discover that module set from the real tree
  (`tests.source_tree.production_modules`) rather than a hand-kept tuple, so
  it already scans wherever this decision's new files land.
- **ADR 0014**: `cli.py` reaches `engine`/`pipeline` only through a *local*
  `from create_forge import engine, pipeline` inside the relevant command's
  own function body, referencing `engine.EngineCompatibilityError` etc. as
  attribute access on the bound module (not a second `from
  create_forge.engine import ForgeEngineError` statement, which
  `mypy --strict`'s `no_implicit_reexport` check would reject). The identical
  shape applies to `runner`/`update`/`engine_source`, imported lazily so a
  plain `pip install create-forge` — `copier` absent, since ADR 0040 moved it
  to the optional `legacy` extra — never fails importing `cli.py` itself.

Verified against the current source (grep, not assumption): `cli.py`'s only
module-scope imports are `capture`, `compat`, `config`, `prompts`,
`registry`, `sources`, `spec`, `staging` — none of `runner`/`pipeline`/
`engine`/`engine_source`/`update` is imported outside a function body, at
twelve call sites across `_ensure_legacy_available`, `new`'s legacy branch,
`_run_scaffold`, `_run_engine`, `_run_engine_source`, `list_templates`,
`update_project`, `_run_copier_update`, `_run_engine_update`,
`_print_recovery`, `_tooling_diagnostics`, and `_gather_diagnostics`.

Also load-bearing and easy to break by a file move: `scripts/
candidate_evidence.py`'s `SAFETY_CLI_FUNCTIONS` names four `cli.py`
module-level functions (`update_project`, `_run_engine_update`,
`_print_recovery`, `_confirm_degraded`) by exact module path and extracts
their source with `ast` to feed the update-safety evidence digest ([ADR
0054](0054-verify-installed-update-safety-on-the-release-candidate.md)
decision 5). ADR 0054 already anticipated this decision by name: "CF-25 ...
will move the `cli.py` functions the digest extracts ... and CF-25 must
re-run the installed suite."

## Decision

1. **Layout: a `commands/` subpackage beside `cli.py`.** `src/create_forge/
   commands/` gains `_output.py` (only what several commands share —
   `console`, `err`, `_harden_console_encoding`; command modules reference
   these module-qualified, e.g. `_output.err`, so a test has one patch
   point), `new.py` (legacy, default-engine, and `--engine-source` `new`
   orchestration), `selection.py` (archetype/capability/platform/option
   resolution helpers `new.py` uses), `catalogue.py` (`list`), `update.py`
   (routing, both update routes, recovery printing — a distinct module from
   the existing engine-free `create_forge/update.py`, disambiguated by
   package path, never imported from each other by mistake since one lives
   under `commands/`), and `config.py` (`config init`/`config show`).
2. **What stays in `cli.py`.** The `app`/`config_app` Typer objects, `main()`
   and its `--version` callback, every `@app.command`/`@config_app.command`
   function signature — so `--help` text and option identity stay visible in
   one file — and the pure option-shape parsing tied directly to those
   signatures (`_parse_data`, `_parse_component_options`). Every command body
   delegates to `commands/*`.
3. **Dependency direction is unchanged, only widened to the new package.**
   CLAUDE.md's existing rule — `cli` → `prompts`/`runner`/`registry`/
   `staging` → `models` — now reads `cli` **and** `commands/*` on the left.
   `commands/*` may import `runner`/`pipeline`/`engine`/`engine_source`/
   `update` only through the exact same lazy, function-body import shape
   `cli.py` uses today, never at module scope; `commands/*` never imports
   `forge_template` or `copier` directly (ADR 0013 unchanged); and
   `commands/*` never imports `cli` — dependencies point one way, into the
   command layer, never back out of it. This **extends** ADR 0014's local-
   import rule and its attribute-access mypy-strict workaround to
   `commands/*`; it does not supersede ADR 0014, which still governs `cli.py`
   itself for anything CF-25.02 leaves there.
4. **A helper moves with its only caller.** `_markers` moves to
   `commands/doctor.py`; `_report_created`/`_confirm_third_party` move to
   `commands/new.py`. Nothing is left behind in `cli.py` "just in case" —
   CF-25.02's own acceptance criteria already require no public-surface
   change, and an unused helper left in `cli.py` would be exactly the kind of
   coupling this decision exists to remove.
5. **Error and exit-code seam: unchanged, not redesigned.** Command modules
   keep raising `typer.Exit(<code>)` and printing through the shared
   `console`/`err` from `commands/_output.py`, exactly as `cli.py` does
   today. A typed-error-mapped-in-`cli.py` alternative was considered and
   rejected: it would touch every one of the ~63 `typer.Exit(...)` call sites
   for no behavioural gain, which is a needless risk in an epic whose own
   acceptance criteria forbid any output or exit-code change.
6. **Approved extraction sequence for CF-25.02**, smallest and most
   self-contained first, each its own reviewable PR-slice:
   1. `commands/_output.py` — a pure lift (console objects, encoding
      hardening); no behaviour can change.
   2. `commands/config.py` — `config init`/`show`; no engine coupling at all.
   3. `commands/doctor.py` — self-contained diagnostics gathering/rendering.
   4. `commands/catalogue.py` — `list`.
   5. `commands/update.py` — routing, both update routes, recovery printing.
      **This slice must also re-point `scripts/candidate_evidence.py`'s
      `CLI_FILE`/`SAFETY_CLI_FUNCTIONS` at the four functions' new home and
      refresh the update-safety evidence record**, per ADR 0054's own
      instruction — a hard, named dependency of this slice, not an
      afterthought.
   6. `commands/new.py` + `commands/selection.py` — the largest lift: legacy,
      engine, and engine-source `new` orchestration, plus archetype/
      component selection.
   Each slice keeps every public option, default, output string, and exit
   code unchanged; runs `uv run poe check` plus `docs/cli-command-map.md`'s
   characterisation tests and any installed suite the slice's own
   `docs/*-validation.md` record names.

## Consequences

- `cli.py` shrinks to the Typer surface alone once CF-25.02 completes all six
  slices; each command's orchestration lives in one focused file a reviewer
  can read without the other four commands' logic alongside it.
- `commands/update.py` and the existing `create_forge/update.py` share a
  stem-adjacent name, distinguished only by package path — CF-25.01 already
  found and fixed one guard (`tests/test_subprocess_policy.py`) that keyed an
  offender dict by bare filename, which would have silently merged the two
  files' findings; any future guard walking `commands/*` and `create_forge/
  *.py` together must key by path, not name, for the same reason.
- `scripts/candidate_evidence.py`'s `SAFETY_CLI_FUNCTIONS`/`CLI_FILE` are a
  hard, named CF-25.02-slice-5 dependency: moving those four functions
  without re-pointing the evidence script and re-running the installed
  update-safety suite leaves `main` red at `tests/
  test_update_safety_evidence.py`, and leaves the evidence describing code
  that no longer exists at the recorded location even if the digest
  happened to still match by accident.
- The 29 `monkeypatch.setattr(cli_module/cli, "<name>")` call sites in
  `test_cli.py`/`test_sources.py`/`test_streamlit_adoption.py`/
  `test_engine_source.py` all need re-pointing at wherever their target
  function lands — CF-25.03's job, using CF-25.01's `docs/
  cli-command-map.md` as the map of what moved where.
- No published artefact, public CLI option/default/output/exit-code, or
  provider-protocol boundary changes; this is an internal module-layout
  decision only.
