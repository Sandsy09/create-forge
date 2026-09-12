# CLI UX and Prompting Conventions

This is the living contributor contract for `create-forge` commands, prompts,
errors, and exit statuses. It records the user experience that future CLI work
must preserve deliberately.

CF-18.01 ([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md))
implemented the accepted target in
[ADR 0010](adr/0010-public-engine-integration-contract.md): `new` with no
route flag now gathers answers directly against the public `forge-template`
engine and ProjectSpec, replacing the released v0.3.x default's registry +
Copier boundary. `--legacy` reaches that prior boundary unchanged. The
input, parity, cancellation, and error-presentation conventions below remain
in force on both routes unless a later decision explicitly revises them;
`--engine-source`/`--engine-ref`, the engine `new` Git/hook lifecycle, and
engine-native `update` dispatch remain undelivered (CF-18.02 through
CF-18.04).

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
   On the current default path this is Copier's `defaults=True`; after the engine cutover it is
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

- `--yes` disables interactive questions. On the default engine path it
  requires a project name **and** `--archetype` (the engine declares no
  default); on `--legacy` it requires a project name. Resolved config values
  and explicit presets are still applied; remaining values use template or
  engine defaults.
- `--template`/`--template-url`/`--ref` are `--legacy`-only: they suppress
  template selection there exactly as before, and are rejected outright
  without `--legacy`. Without `--template`, a single selectable template is
  chosen without asking; otherwise the configured or bundled default is
  offered first.
- A positional argument or `--data` preset suppresses the matching question.
- A conditional question is skipped when its declared prerequisite is not
  satisfied (`--legacy` only — the default engine path has no conditional
  registry questions).
- Questions intentionally absent from the CLI prompt catalogue are left to
  template or engine defaults.
- On the default engine path, an explicit `--capability`/`--no-capabilities`
  (or the platform pair) suppresses that kind's selection prompt, and a
  `--component-option` preset suppresses that option's prompt — see the
  canonical [component selection contract](component-selection.md).
- On the default engine path, a component kind with no discovered
  descriptors is never prompted.

`--legacy`'s `--template-url` escape hatch always prints its code-execution
warning. It asks for confirmation unless `--yes` was supplied.

[ADR 0011](adr/0011-engine-source-and-version-resolution.md) specifies the
`--engine-source`/`--engine-ref` engine-package override, and the
[engine resolution contract](engine-resolution.md) records it in full.
[ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md)
supersedes ADR 0011 on one point: `--template-url`/`--ref` are *retained*,
scoped to the explicit `--legacy` route, rather than replaced — the
direct-Copier path stays supported. `--engine-source`/`--engine-ref` are a
new, orthogonal pair that select the engine *distribution* itself, not yet
implemented (CF-18.02).

## The default engine `new` path

`new` with no route flag builds, validates, renders, and finalises through
the public `forge-template` engine instead of Copier — see
[ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md)
(CF-18.01, which made this the default architecture),
[ADR 0014](adr/0014-lazy-engine-reachability.md) (superseded on the
default-vs-hidden point; its guarded-import *shape* now protects `--legacy`'s
Copier-touching modules instead),
[ADR 0015](adr/0015-staged-filesystem-generation.md),
[ADR 0017](adr/0017-cli-application-archetype-exposure.md),
[ADR 0025](adr/0025-engine-native-prompt-flow.md), and the canonical
[ProjectSpec construction](project-spec-construction.md) and
[filesystem generation](filesystem-generation.md) contracts. `forge-template`
is a required dependency (ADR 0040 decision 1) — a plain
`pip install create-forge` / `uvx create-forge` resolves it, so this is the
route reached with no extra install step at all. Since #91
([ADR 0025](adr/0025-engine-native-prompt-flow.md)), it reads no registry
data at all: it discovers the archetype catalogue, resolves which archetype
to build, then prompts directly for that archetype's own ProjectSpec-identity
answers and declared `ComponentDescriptor.options` — a genuinely separate
prompt flow from `--legacy`'s, not a shared one. `--template`,
`--template-url`, and `--ref` are therefore rejected outright without
`--legacy`, mirroring `--archetype`'s rejection under `--legacy` in reverse.
It stages and moves a successful render into place exactly as `--legacy`
does — `--dry-run` lists the planned targets and writes nothing, on both
routes alike. `forge-template`'s production catalogue ships `library`, `cli`,
and `data-science` (plus the `github` platform and eight tooling
capabilities), so this route generates a real project when given a valid
archetype. A project it creates today is not yet `create-forge
update`-able — the committed generation-metadata file and engine-native
update dispatch are CF-18.03/CF-18.04's job; it is not eligible for the
`--legacy` Copier update path either, since it writes no
`.copier-answers.yml`.

`--engine-preview` — the hidden, development-only precursor to this route —
was removed outright at the cutover, with no deprecation window: it was
hidden and undocumented, so it carried no compatibility promise. An unknown
`--engine-preview` today is a plain Typer usage error, exit `2`.

An `--archetype` option selects which engine archetype to build, resolved
against `pipeline.discover_archetypes()` — the real, discovered catalogue,
filtered to `kind == "archetype"`. An explicit `--archetype` not present in
that catalogue is rejected before any engine call. Omitting it with `--yes`
is rejected outright, naming the available ids: the engine declares no
default archetype, and `templates.toml`'s `default_template` is a
`--legacy`-path concept this selection does not inherit. Omitting it
interactively falls to a prompt (`prompts.choose_archetype`), the *only*
"What are you building?" prompt on this path since #91 — there is no longer
a separate template selection ahead of it. `--archetype` combined with
`--legacy` is rejected as contradictory rather than silently ignored.

Once an archetype is resolved, CF-13.03
([ADR 0028](adr/0028-discovery-driven-component-selection.md)) resolves the
capabilities and platforms to select alongside it — from `--capability` /
`--no-capabilities` / `--platform` / `--no-platforms`, or an interactive
multi-select per kind ("Which capabilities?", "Which platforms?"), skipped
when the flag was given, the kind has no discovered descriptors, or every
descriptor of it is required by the archetype. All of that precedes any
project answer. Then `prompts.ask_project_answers` asks the three
CLI-collected answers that reach `ProjectSpec.project`
(`project_name`/`project_description`/`license`), and
`prompts.resolve_component_options` asks exactly what every *selected*
component's own discovered descriptor declares (CF-13.04,
[ADR 0029](adr/0029-per-component-option-collection.md)) — in composition-tier
then lexical order, and omitting a component whose namespace stays empty.
`library` declares options (`packaging_mode`/`initial_version`); `cli` and
`data-science` declare none, so a selected optionless component is never
prompted and serialises no namespace:

| Registry question | Reaches ProjectSpec for `library`? | for `cli` / `data-science` (+ capabilities)? |
| --- | --- | --- |
| `project_name`, `project_description`, `license` | asked directly | asked directly |
| `packaging_mode`, `initial_version` | asked directly, from `library`'s own descriptor | n/a — no options declared |
| `github_org`, `type_checking`, `use_docs` | discarded | discarded |

ADR 0040 decision 10 (CF-18.01) retired the legacy `build_backend`/
`versioning` → `packaging_mode` `--data` fallback CF-08.03's archetype-parity
review ([ADR 0019](adr/0019-cli-archetype-parity-review.md)) had added: a
caller now sets `library.packaging_mode` only through
`--component-option library.packaging_mode=<value>`, like any other
component option — never a `build_backend`/`versioning` answer key.

Separately, [ADR 0025](adr/0025-engine-native-prompt-flow.md) fixed the
double "What are you building?" prompt CF-08.03's review had tracked as a
known limitation ([#91](https://github.com/Sandsy09/create-forge/issues/91)):
the destination is now only fully known once a project name has been
collected, so the non-empty-destination check splits in two — an explicit
`--path` is still checked before the engine is imported at all, preserving
that guarantee for the common case; the final destination is checked again
immediately before any ProjectSpec construction, validation, or render
begins, still before every side effect that writes anything.
`discover_components()` itself reads the installed catalogue and writes
nothing, so running it ahead of a not-yet-knowable destination introduces no
new filesystem risk.

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

## Component selection

The canonical [component selection contract](component-selection.md) defines
how the default engine path turns flags and prompts into a ProjectSpec's
`components` and `component_options`: `--capability`/`--platform` (repeatable),
`--no-capabilities`/`--no-platforms`, and
`--component-option ID.OPTION=VALUE`. All five are visible, engine-path-only
flags — rejected with exit `1` in combination with `--legacy`, exactly as
`--archetype` is. CF-13.03
([ADR 0028](adr/0028-discovery-driven-component-selection.md)) implemented the
four capability/platform flags and their interactive multi-selects; CF-13.04
([ADR 0029](adr/0029-per-component-option-collection.md)) implemented
`--component-option`, per-component option collection for every selected
component, and CLI-string-to-declared-type coercion. CF-13.05
([ADR 0030](adr/0030-data-science-preview-pipeline-validation.md)) then proved
the whole pipeline against the released engine for the Data Science
composition — see the canonical
[Data Science preview-pipeline validation](data-science-preview-validation.md).
ADR 0040 decision 8 (CF-18.01) un-hid all five with their names unchanged and
removed `--engine-preview`, making this the default `new` path's own surface.

For this document's purposes: a malformed `--component-option` (missing `.` or
`=`) is a `typer.BadParameter` usage rejection, exit `2`, like a malformed
`--data`. Every other selection failure `create-forge` raises itself — one of
these five flags combined with `--legacy`, a contradictory
`--capability`/`--no-capabilities` pair, an unknown or wrong-kind component
id, an option for an unselected component — is exit `1`. Cancelling a
selection prompt is exit `130` with nothing written. Missing requirements,
conflicts, and invalid option values stay engine-owned and are translated
through `engine.explain`.

## Engine-default CLI

The canonical [engine-default CLI contract](engine-default-cli.md)
([ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md), the
first child of [CF-EPIC-16](https://github.com/Sandsy09/create-forge/issues/152))
defined the command surface for the engine-default cutover. CF-18.01 has
implemented most of it:

- the engine is a required dependency and the default `new` route; `copier`
  is the optional `legacy` extra, reached through the visible `--legacy` flag
  that scopes `--template`/`--template-url`/`--ref`;
- `--template-url`/`--ref` are retained rather than replaced (superseding
  [ADR 0011](adr/0011-engine-source-and-version-resolution.md) on that
  clause);
- `--engine-preview` is removed and the five selection flags above are
  visible with names unchanged;
- `list` prints the discovered catalogue; `list --legacy` prints the
  registry; `doctor` negotiates against the real engine while staying
  offline, populating `projectspec_protocol.detected`,
  `component_manifest_protocol`, and `metadata_version`;
- exit `3` widened to also cover an engine that cannot be imported at all
  and `--legacy` without the extra installed.

Still open: `--engine-source`/`--engine-ref` — a new, orthogonal engine-package
override that provisions an isolated environment and whose renders write no
generation metadata (CF-18.02); the engine `new` Git/hook lifecycle
(CF-18.03); engine-native `update` dispatch (CF-18.04); deeper `--legacy`
regression and old-preview-project recovery (CF-18.05); and the concrete
deprecation versions, windows, acceptance matrix and support policy CF-16.03
fixed in the
[engine-default cutover acceptance contract](engine-cutover-acceptance.md)
([ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md)), which
remain CF-18.06/CF-18.07's to execute and publish. The full decision record
lives in `docs/engine-default-cli.md`; update it and this section together
when a rule it still describes as pending ships.

## Update dry runs

`update --dry-run` validates a Copier update without applying it to the target
project. It performs the same source and `--ref` resolution, safety checks, and
template rendering as a real update, but calls Copier with `pretend=True`. A
successful run leaves the project's visible files, `.copier-answers.yml`, Git
HEAD, index, and working-tree status unchanged and reports `Dry run complete.
No project files changed.` instead of claiming the project was updated.

Copier's update merge intentionally suppresses per-file status because it
cannot report those changes reliably, so this is a validation preview rather
than a file-by-file diff. Template resolution and temporary rendering may still
occur. Missing answers, a dirty or non-Git project, template resolution errors,
and other application failures retain exit status `1` and never print the
success message. Omitting the flag preserves the normal update and its existing
`Updated`/review-the-diff guidance.

Projects generated through the default engine `new` path remain ineligible
for `update` because they do not contain `.copier-answers.yml`; `--dry-run`
does not change that boundary.

`update` will gain an engine-native route
(CF-16.02, [ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md),
canonical [engine project lifecycle contract](engine-project-lifecycle.md)):
`update` routes to it when the project holds a committed
`.forge/generation.json`, to the Copier path above when it holds only
`.copier-answers.yml`, and `update --legacy` forces the Copier path. The
engine-native route runs a Git-backed three-way merge from a clean working
tree, so `--dry-run` there prints a genuine per-target classification list
(`added` / `changed` / `removed` / `renamed`, each clean or CONFLICT) rather
than the change/no-change summary Copier's merge is limited to. That route is
decided by CF-16.02 and built by
[CF-18.04](https://github.com/Sandsy09/create-forge/issues/161); it has not
shipped.

## Engine project lifecycle

The canonical [engine project lifecycle contract](engine-project-lifecycle.md)
(CF-16.02, [ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md))
defines what happens **after the engine renders a project** and **when
`create-forge update` runs against one**, after the cutover:

- the engine `new` path, after its staged render and atomic rename, runs
  `git init` + one initial commit at the final destination, and
  `pre-commit install --install-hooks` only when the render produced a
  `.pre-commit-config.yaml`; a failure of any of these keeps the project and
  warns rather than discarding a sound render;
- `create-forge` persists `forge-template`'s generation-metadata document as a
  committed `.forge/generation.json` — the engine analogue of
  `.copier-answers.yml` — and rewrites it, last, after every successful
  update;
- an engine-native update requires a clean Git working tree, applies rename
  records before diffing, writes inline conflict markers, deletes a `removed`
  target only if pristine, never touches a `skip-if-exists` target, and leaves
  the result staged for the user to review and commit;
- recovery from a failed or cancelled update is `git restore . && git clean
  -fd`, which `create-forge` prints but never runs itself;
- an unavailable recorded engine release fails closed, with an opt-in
  (`--degraded`, or an interactive prompt) two-way update that records
  `reproduction.mode = "degraded"`;
- update failures reuse the exit-status table above unchanged — `1` for a
  dirty tree / bad merge / missing metadata / no route, `3` for an
  incompatible or unavailable recorded engine, `130` for cancellation.

That contract is a decision, not a shipped interface. `new` reaches the
engine path by default since CF-18.01, but until
[CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) onward
implement this contract, an engine-generated project writes no committed
generation metadata and `update` still handles only direct-Copier projects.

## Engine-default cutover acceptance

The canonical
[engine-default cutover acceptance contract](engine-cutover-acceptance.md)
(CF-16.03, [ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md))
fixes **how the cutover is accepted and supported** — the parts CF-16.01 and
CF-16.02 deferred: the cutover is a single tagged **`create-forge 0.4.0`**
release; the supported operating systems (Linux and Windows proven, macOS
unclaimed), Python versions (the latest four final CPython releases, today
3.11–3.14) and install modes (`uvx`, `uv tool install`, `pip`, and the
`legacy` extra); the cross-repository acceptance matrix and release gates
(provider publishes first; both integrated validations and working
engine-native **and** legacy updates before `create-forge` publishes); the
release-rollback rule (immutable-forward, yank the defective version); the
`create-forge 0.3.x` support window (≥ 90 days and ≥ 1 further tagged release
past the cutover); and the deprecation window (≥ 90 days and ≥ 1 release, no
calendar dates). It is a decision only — the implementation, matrix execution
and publication are
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153).

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

Template sources are validated before `new` asks any questions, including
the third-party confirmation; `--yes` and `--dry-run` do not bypass validation.
HTTP(S) user-info (even username-only or encoded), SSH URL passwords, URL
queries/fragments, malformed authorities, and control characters fail with
exit `1`. Copier's `git+` and `gh:`/`gl:` forms receive the same checks, while
ordinary SSH usernames, SCP-style sources, and local paths remain supported.
Accepted source strings and `--ref` values reach Copier unchanged. Source
warnings use literal text rather than interpreting source characters as Rich
markup; authentication, queries, and fragments are defensively removed.

`update` validates the recorded `.copier-answers.yml` `_src_path` before
invoking Copier. Missing or malformed source metadata also fails with exit
`1`, without rewriting the answers file or changing project contents. Errors
identify the affected option or metadata field without echoing its value and
recommend credential helpers or SSH agents; URL query/fragment errors point
to `--ref` for version selection. See [ADR 0036](adr/0036-template-source-credentials.md).

| Status | Meaning | Examples |
| --- | --- | --- |
| `0` | The command completed successfully. | Successful commands, `--help`, and `--version`. |
| `1` | Parsing succeeded, but the application could not complete the request. | Malformed config, an unknown template, a missing project name (and, on the default engine path, a missing `--archetype`) under `--yes`, failed `doctor` checks, scaffold/update failures, a non-empty destination, a staging/finalisation failure ([ADR 0015](adr/0015-staged-filesystem-generation.md)), or a selection failure `create-forge` rejects itself — one of the five selection flags combined with `--legacy`, a contradictory `--capability`/`--no-capabilities` pair, an unknown or wrong-kind component id, or an option for an unselected component ([component selection contract](component-selection.md)). |
| `2` | The command invocation is invalid and Typer rejects its usage. | An unknown command or option, an unrecognised flag such as the retired `--engine-preview`, malformed `--data` without `key=value`, or a malformed `--component-option` without `ID.OPTION=VALUE`. |
| `3` | The required generator is missing or unusable: an installed or overridden engine, or its ProjectSpec/component-manifest protocol or `metadata_version`, is outside the range this CLI supports, the engine cannot be imported at all, or `--legacy` was given without the `legacy` extra installed. | Assigned by [ADR 0011](adr/0011-engine-source-and-version-resolution.md); implemented at the engine boundary by [ADR 0013](adr/0013-projectspec-construction-boundary.md)'s `engine.EngineCompatibilityError`. Widened at the cutover by ADR 0040 decision 12 (CF-18.01) to cover the whole provider-availability class — reachable on the now-default engine `new` path, not only a hidden flag. |
| `130` | The user cancelled an interactive operation. | Ctrl-C/Ctrl-D at a question, or declining the third-party source confirmation. |

Cancellation must not invoke scaffolding. Expected application failures are
shown without a traceback and phrased as an action the user can take.
Git failures while resolving, cloning, refreshing, checking out, or preparing
a template repository follow that same exit-`1` contract. `runner.py` catches
Copier's `ProcessExecutionError` boundary and reports checks for the template
URL, `--ref`, network, repository access, and Git credentials. It never echoes
the raw Git command, stdout, stderr, source, or ref because those details may
contain credentials. Unrelated exceptions are not converted into user errors.
Unrecognised `CopierError` messages likewise use fixed template/answers/ref
guidance rather than repeating raw exception text. Original causes remain
internal; normal error rendering never prints their chains.

An unusable Copier template cache (Copier `>=9.16`) is a distinct exit-`1`
condition ([ADR 0039](adr/0039-copier-cache-diagnostics.md)). It is recognised
from fixed signals only -- a `not a git repository` phrase in stderr that also
names the resolved cache directory, or an `OSError` Copier raises directly
while creating that directory -- and answered with `COPIER_CACHE_DIR` recovery
guidance for PowerShell and POSIX shells. The message names only create-forge's
own resolved cache path; argv, stdout, and stderr are still never emitted. An
`OSError` whose path is not under the cache directory re-raises untouched
rather than being disguised as a user error.

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

It does not own generated-project schema or compatibility rules. On the default Copier path,
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
  the `test_update_*` command cases,
  `test_new_bad_data_format_is_rejected`, the two
  `test_new_aborting_*_exits_130` cases,
  `test_new_template_url_declined_scaffolds_nothing`, and the
  `test_new_engine_preview_*`/`test_new_without_engine_preview_is_unchanged`
  group covering the `--engine-preview` flag from ADR 0014, its ADR 0015
  finalisation, and its ADR 0017 `--archetype` selection surface (explicit,
  `--yes`-without-one, unknown-id, and interactive-prompt cases). The
  "engine-native prompting" block (ADR 0025) covers #91's acceptance criteria
  directly: `test_new_engine_preview_cli_archetype_asks_no_library_question`,
  `test_new_engine_preview_library_archetype_asks_declared_options_only`
  (including the resolved `component_options`), `test_new_engine_preview_never_loads_the_registry`,
  `test_new_engine_preview_interactive_asks_what_are_you_building_once`,
  `test_new_engine_preview_rejects_copier_only_flags`, and
  `test_new_engine_preview_yes_legacy_data_still_derives_packaging_mode`.
- [`tests/test_staging.py`](../tests/test_staging.py) covers destination
  conflict detection, target-safety refusals, staging placement and atomic
  finalisation, and cleanup after failure — see the canonical
  [filesystem generation contract](filesystem-generation.md).
- [`tests/test_runner.py`](../tests/test_runner.py) covers the narrow Copier/Git
  process-failure boundary, including a real missing repository, sanitized
  credential-bearing diagnostics, exception chaining, and destination cleanup.
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
  selection, and cancellation cases (ADR 0017). `ask_project_answers`,
  `ask_component_options` (ADR 0025), `resolve_component_options` and
  `coerce_option_value` (ADR 0029) have their own preset/defaults/
  cancellation cases, plus one per declared option `type` (`string` with and
  without `choices`, `boolean`, `integer`, `string_list`), the empty-return
  case for a descriptor that declares none, and — for
  `resolve_component_options` — multi-descriptor ordering and undeclared-key
  pass-through.
- [`tests/test_drift.py`](../tests/test_drift.py) covers the default-path boundary
  between registry presentation metadata and template-owned questions,
  choices, conditions, and defaults.
- [`tests/test_update.py`](../tests/test_update.py) exercises a real Copier
  update against a local two-tag template, including the dry-run no-change
  guarantee followed by a successful real update, plus a missing-source failure
  that leaves the project and Git state unchanged.
- The `--engine-preview` component-selection surface is its own canonical
  [component selection contract](component-selection.md), characterized by
  `tests/test_engine_cross_repository.py`'s
  `test_selection_model_matches_the_documented_contract`, and by
  `tests/test_component_selection.py`, `tests/test_prompts.py`, and
  `tests/test_pipeline.py` (CF-13.03, CF-13.04). The Data Science composition
  through that surface is proven by `tests/test_data_science_pipeline.py`
  (CF-13.05), mapped to the epic checklist by the canonical
  [Data Science preview-pipeline validation](data-science-preview-validation.md).
- [`tests/test_e2e_installed_rollout.py`](../tests/test_e2e_installed_rollout.py)
  (CF-14.03, [ADR 0033](adr/0033-complete-rollout-regression-validation.md))
  re-proves the exit-status table and the `doctor --json` diagnostics through
  the *installed* `0.3.0` console script:
  `test_installed_failure_case_is_rejected_cleanly` covers exit `1` and `2`
  across the selection / option / template-flag / malformed-input surface,
  `test_out_of_range_engine_is_rejected_before_any_write` covers exit `3`, and
  the `test_engineless_*` cases cover the no-engine command surface. The
  canonical [rollout regression and failure validation](rollout-regression-validation.md)
  maps each to #113's acceptance criteria.

When a change intentionally alters one of these conventions, update this
document and its characterization test in the same pull request.
