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

## Interactive and non-interactive parity

Interactive prompts are an input mechanism, not a separate generation path.
After answer collection, interactive and non-interactive invocations converge
on the same source, answers, destination, template ref, dry-run setting, and
`ScaffoldRequest`. Equivalent resolved inputs must therefore produce the same
Copier invocation today and the same ProjectSpec/engine invocation after the
cutover.

For `new`, no scaffold call or destination write may occur before answer
collection and any required source confirmation have completed. Cancelling
either stage leaves the scaffold uninvoked.

## Exit statuses

| Status | Meaning | Examples |
| --- | --- | --- |
| `0` | The command completed successfully. | Successful commands, `--help`, and `--version`. |
| `1` | Parsing succeeded, but the application could not complete the request. | Malformed config, an unknown template, a missing project name under `--yes`, failed `doctor` checks, or scaffold/update failures. |
| `2` | The command invocation is invalid and Typer rejects its usage. | An unknown command or option, or malformed `--data` without `key=value`. |
| `3` | *Reserved.* An installed or overridden template engine, or its ProjectSpec protocol, is outside the range this CLI supports. | Not yet raised — no code path can produce it under the v0.1.x direct-Copier line. Assigned by [ADR 0011](adr/0011-engine-source-and-version-resolution.md); ships at the engine cutover. |
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

## Executable examples

The contract is characterized by these tests:

- [`tests/test_cli.py`](../tests/test_cli.py) covers resolved
  `ScaffoldRequest` values, exit statuses, cancellation without scaffolding,
  config and `--data` precedence, the third-party warning, and application
  error presentation. In particular, see
  `test_new_dry_run_records_the_request_and_writes_nothing`,
  `test_new_bad_data_format_is_rejected`, the two
  `test_new_aborting_*_exits_130` cases, and
  `test_new_template_url_declined_scaffolds_nothing`.
- [`tests/test_prompts.py`](../tests/test_prompts.py) covers preset suppression,
  config pre-filling, derived defaults, conditional questions, and automatic
  single-template selection through `test_ask_all_does_not_reprompt_a_preset_key`,
  `test_defaults_pre_fill_a_text_prompt_without_suppressing_it`, and their
  neighbouring cases.
- [`tests/test_drift.py`](../tests/test_drift.py) covers the v0.1.x boundary
  between registry presentation metadata and template-owned questions,
  choices, conditions, and defaults.

When a change intentionally alters one of these conventions, update this
document and its characterization test in the same pull request.
