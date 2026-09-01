# CLI UX and Prompting Conventions

This is the living contributor contract for `create-forge` commands, prompts,
errors, and exit statuses. It records the user experience that future CLI work
must preserve deliberately.

The released v0.1.x implementation gathers answers from a bundled registry and
calls Copier directly. The accepted target in [ADR 0010](adr/0010-public-engine-integration-contract.md)
replaces that boundary with the public `forge-template` engine and ProjectSpec.
The implementation-specific mechanisms below will change at that cutover; the
input, parity, cancellation, and error-presentation conventions remain in
force unless a later decision explicitly revises them.

## Input resolution and prompt defaults

Configuration, explicit inputs, and prompts have different jobs:

1. The config file is loaded first, then matching `FORGE_*` environment
   variables override its values.
2. Config values pre-fill questions that the CLI asks. They do not suppress
   those questions, so accepting or replacing the displayed value produces the
   interactive answer.
3. The positional project name and `--data key=value` are explicit presets.
   A preset suppresses the corresponding prompt. If both the positional name
   and `--data project_name=...` are supplied, the `--data` value wins.
4. Values the CLI does not ask for are resolved by the template-owned defaults.
   In v0.1.x this is Copier's `defaults=True`; after the engine cutover it is
   ProjectSpec and engine validation.

Within an interactive question, a default derived from an earlier answer takes
priority over config, and config takes priority over the registry's presentation
default. The current example is deriving a repository slug from the project
name. A presentation default must remain aligned with the template-owned
default; it does not become a second semantic source of truth.

`--data` parses case-insensitive `true` and `false` as booleans and otherwise
passes the value as text. Repeated keys use the last `--data` value.

## When prompts are skipped

Prompting is omitted only when the answer or decision is already explicit:

- `--yes` disables interactive questions and requires a project name. Resolved
  config values and explicit presets are still applied; remaining values use
  template defaults.
- `--template` suppresses template selection. Without it, a single selectable
  template is chosen without asking; otherwise the configured or bundled
  default is offered first.
- A positional argument or `--data` preset suppresses the matching question.
- A conditional question is skipped when its declared prerequisite is not
  satisfied.
- Questions intentionally absent from the CLI prompt catalogue are left to
  template defaults.

The current `--template-url` escape hatch always prints its code-execution
warning. It asks for confirmation unless `--yes` was supplied. This behavior
remains authoritative for v0.1.x; the compatible local/VCS engine override
described by the [integration contract](integration-contract.md) replaces it
only at the coordinated engine cutover.

[ADR 0011](adr/0011-engine-source-and-version-resolution.md) specifies that
replacement's interface — `--engine-source`/`--engine-ref` — and the
[engine resolution contract](engine-resolution.md) records it in full. Until
the cutover ships it, `--template-url`/`--ref` above are the only source and
version options this CLI accepts; the new names are not yet implemented.

## The `--engine-preview` development flag

`new --engine-preview` is a hidden, development-only option (absent from
`--help`) that builds, validates, renders, and finalises through the public
`forge-template` engine instead of Copier — see
[ADR 0014](adr/0014-lazy-engine-reachability.md),
[ADR 0015](adr/0015-staged-filesystem-generation.md),
[ADR 0017](adr/0017-cli-application-archetype-exposure.md), and the canonical
[ProjectSpec construction](project-spec-construction.md) and
[filesystem generation](filesystem-generation.md) contracts. It always
prints an informational note that it is a hidden preview path, unconditionally
and regardless of `--yes` — but unlike `--template-url`'s warning, this is
not a confirmation gate: `forge-template` is a reviewed dependency (the
optional `engine` extra, ADR 0018), not arbitrary user-supplied code, so
there is no code-execution trust question to ask. It reuses the same answer
collection and destination computation as the Copier path (no parallel
prompt flow), rejects a non-empty destination before any engine call, and
stages and moves a successful render into place exactly as the Copier path
does — `--dry-run` lists the planned targets and writes nothing, on both
paths alike. Since CF-08.02, `forge-template`'s production catalogue ships
both `library` and `cli`, so `--engine-preview` generates a real project
when given a valid archetype -- reachable since #9/ADR 0018 with nothing
more than `pip install 'create-forge[engine]'`, not a source checkout.
`--engine-source`/`--engine-ref` above remain the names reserved
for the eventual public override; `--engine-preview` is a distinct,
temporary flag retired at the coordinated cutover, not renamed into that
pair. A project it does create is not `create-forge update`-able — it writes
no `.copier-answers.yml`.

A hidden `--archetype` option selects which engine archetype to build,
resolved against `pipeline.discover_archetypes()` — the real, discovered
catalogue, filtered to `kind == "archetype"`. An explicit `--archetype` not
present in that catalogue is rejected before any engine call. Omitting it
with `--yes` is rejected outright, naming the available ids: the engine
declares no default archetype, and `templates.toml`'s `default_template` is
a Copier-path concept this selection does not inherit. Omitting it
interactively falls to a prompt (`prompts.choose_archetype`), mirroring
`choose_template`'s shape including its skip-when-only-one-exists behaviour.
`--archetype` without `--engine-preview` is rejected rather than silently
ignored.

CF-08.03's archetype-parity review ([ADR 0019](adr/0019-cli-archetype-parity-review.md))
recorded that reusing the Copier registry's answer collection means the
prompt set stays Library-shaped for every archetype, since `templates.toml`
has one template:

| Registry question | Reaches ProjectSpec for `library`? | for `cli`? |
| --- | --- | --- |
| `project_name`, `project_description`, `license` | yes | yes |
| `build_backend`, `versioning` | yes, via `map_legacy_library_options` | discarded |
| `github_org`, `type_checking`, `use_docs` | discarded | discarded |

The archetype is also selected *after* these answers are collected, so a
user building a CLI Application still answers `build_backend`/`versioning`
before it is silently dropped. This is accepted as a known limitation of
reusing the Copier answer flow, not fixed by that review — doing so would
mean the engine path stops sharing this section's "no parallel prompt flow"
and "before any engine call" guarantees, both open questions tracked by
[#91](https://github.com/Sandsy09/create-forge/issues/91) rather than decided
here.

No command accepts an organisation-policy document or path. CF-09.01
([ADR 0022](adr/0022-downstream-organisation-policy-hook.md)) delivered a
downstream policy-consumption hook at the `pipeline.build_generation_request`
level, not a CLI-facing one — there is no `--policy` flag, no `config.toml`
policy section, and no new exit status. `--archetype`'s explicit/`--yes`/
prompt resolution above is unchanged; it now additionally records, for a
policy-aware *caller of the pipeline*, whether the chosen archetype was an
explicit choice, but that fact affects no user-visible behaviour of `new`
itself. See the canonical
[downstream policy-consumption contract](organisation-policy-consumption.md).

## Interactive and non-interactive parity

Interactive prompts are an input mechanism, not a separate generation path.
After answer collection, interactive and non-interactive invocations converge
on the same source, answers, destination, template ref, dry-run setting, and
`ScaffoldRequest`. Equivalent resolved inputs must therefore produce the same
Copier invocation today and the same ProjectSpec/engine invocation after the
cutover.

For `new`, no scaffold call or destination write may occur before answer
collection and any required source confirmation have completed. Cancelling
either stage leaves the scaffold uninvoked. On both the Copier and engine
paths, a non-empty destination is rejected before any other side effect —
see the canonical [filesystem generation contract](filesystem-generation.md)
for the full staging, finalisation, and cleanup rules ADR 0015 introduces.

## Exit statuses

| Status | Meaning | Examples |
| --- | --- | --- |
| `0` | The command completed successfully. | Successful commands, `--help`, and `--version`. |
| `1` | Parsing succeeded, but the application could not complete the request. | Malformed config, an unknown template, a missing project name under `--yes`, failed `doctor` checks, scaffold/update failures, a non-empty destination, or a staging/finalisation failure ([ADR 0015](adr/0015-staged-filesystem-generation.md)). |
| `2` | The command invocation is invalid and Typer rejects its usage. | An unknown command or option, or malformed `--data` without `key=value`. |
| `3` | *Reserved.* An installed or overridden template engine, or its ProjectSpec protocol, is outside the range this CLI supports. | Assigned by [ADR 0011](adr/0011-engine-source-and-version-resolution.md); implemented at the engine boundary by [ADR 0013](adr/0013-projectspec-construction-boundary.md)'s `engine.EngineCompatibilityError`. Reachable today only via the hidden `new --engine-preview` flag ([ADR 0014](adr/0014-lazy-engine-reachability.md)) — the default `new` path is still v0.1.x direct-Copier and cannot produce it. |
| `130` | The user cancelled an interactive operation. | Ctrl-C/Ctrl-D at a question, or declining the third-party source confirmation. |

Cancellation must not invoke scaffolding. Expected application failures are
shown without a traceback and phrased as an action the user can take.

`doctor --json` prints the same facts as the table — see
[docs/engine-resolution.md](engine-resolution.md)'s diagnostics contract for
the field list — as a single JSON object on stdout instead, with no table
markup. It follows the same exit-status rule as the table form: `0` when
every check passes, `1` when any does not.

## Validation ownership

`create-forge` owns validation needed to operate its interface safely:

- command syntax and option shape;
- prompt completion, including a usable project name from which to derive a
  destination slug;
- template selection, local configuration, and target-directory checks; and
- presentation of user-facing diagnostics.

It does not own generated-project schema or compatibility rules. In v0.1.x,
`forge-template`'s `copier.yml` is authoritative for question types, defaults,
choice domains, conditional semantics, and generated-project validation. The
bundled registry contains the presentation metadata Questionary needs, but it
is not a second policy source. Its mirrored keys, choices, simple conditions,
and default coverage are checked against the released template by the network
drift suite.

At the accepted engine cutover, `forge-template` owns the canonical ProjectSpec
types, semantic validation, and component compatibility. `create-forge` may
translate a Copier or engine failure into actionable terminal guidance; it must
not reproduce the template or ProjectSpec validation predicate in CLI code.
[ADR 0013](adr/0013-projectspec-construction-boundary.md) and the canonical
[ProjectSpec construction contract](project-spec-construction.md) state this
precisely as create-forge maps, forge-template validates: `spec.py` places
answers into their canonical position and validates nothing; `engine.py`
negotiates the protocol and calls the engine's own validation, translating its
structured errors rather than reimplementing their predicates.

## Executable examples

The contract is characterized by these tests:

- [`tests/test_cli.py`](../tests/test_cli.py) covers resolved
  `ScaffoldRequest` values, exit statuses, cancellation without scaffolding,
  config and `--data` precedence, the third-party warning, and application
  error presentation. In particular, see
  `test_new_dry_run_records_the_request_and_writes_nothing`,
  `test_new_bad_data_format_is_rejected`, the two
  `test_new_aborting_*_exits_130` cases,
  `test_new_template_url_declined_scaffolds_nothing`, and the
  `test_new_engine_preview_*`/`test_new_without_engine_preview_is_unchanged`
  group covering the `--engine-preview` flag from ADR 0014, its ADR 0015
  finalisation, and its ADR 0017 `--archetype` selection surface (explicit,
  `--yes`-without-one, unknown-id, and interactive-prompt cases).
- [`tests/test_staging.py`](../tests/test_staging.py) covers destination
  conflict detection, target-safety refusals, staging placement and atomic
  finalisation, and cleanup after failure — see the canonical
  [filesystem generation contract](filesystem-generation.md).
- [`tests/test_e2e_generation.py`](../tests/test_e2e_generation.py) runs the
  real console script against a released template, proving the generated
  tree, its recorded answers, and its own `poe check` — not resolved values,
  the genuine thing. See the canonical
  [end-to-end tests contract](end-to-end-tests.md) and
  [ADR 0016](adr/0016-end-to-end-reference-client-tests.md).
- [`tests/test_prompts.py`](../tests/test_prompts.py) covers preset suppression,
  config pre-filling, derived defaults, conditional questions, and automatic
  single-template selection through `test_ask_all_does_not_reprompt_a_preset_key`,
  `test_defaults_pre_fill_a_text_prompt_without_suppressing_it`, and their
  neighbouring cases, plus `choose_archetype`'s equivalent skip-when-one,
  selection, and cancellation cases (ADR 0017).
- [`tests/test_drift.py`](../tests/test_drift.py) covers the v0.1.x boundary
  between registry presentation metadata and template-owned questions,
  choices, conditions, and defaults.

When a change intentionally alters one of these conventions, update this
document and its characterization test in the same pull request.
