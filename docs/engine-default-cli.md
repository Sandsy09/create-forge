# Engine-Default CLI

This is the living contributor contract for the `create-forge` command surface
**after the engine-default cutover** — the release in which the
`forge-template` engine replaces direct Copier as the default `new` path. It
fixes the default route, the explicit legacy route, installation, `list` and
`doctor` behaviour, generic component selection, answer precedence,
cancellation and non-interactive rules, the `--engine-source` /
`--engine-ref` override, exit statuses, post-generation messaging, and the
order in which today's preview surface is retired.

It decides no runtime behaviour and ships nothing. Like
[`docs/engine-default-parity.md`](https://github.com/Sandsy09/forge-template/blob/main/docs/engine-default-parity.md)
on the provider side, it introduces no protocol increment, no new component,
no `copier.yml` change, and no package version bump. The *rules* below are the
contract; the release that implements them is
[CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) and its
siblings, and the concrete version numbers, windows, acceptance matrix and
support policy are CF-16.03's, in the
[engine-default cutover acceptance contract](engine-cutover-acceptance.md).

It is a sibling of [`docs/cli-conventions.md`](cli-conventions.md) (which keeps
the exit-status table and the pre-cutover behaviour it already documents), the
[component selection contract](component-selection.md) (the selection surface
this contract makes visible), and the
[engine resolution contract](engine-resolution.md) (how the engine package is
obtained, overridden and rejected). Every semantic rule about components,
composition, rendering and generated content stays owned by `forge-template`.

## Status

Accepted as a contract under
[ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md), the
first child of
[CF-EPIC-16 / #152](https://github.com/Sandsy09/create-forge/issues/152). Its
design gate is the four accepted `forge-template` Stage 15 contracts —
[engine-default-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/engine-default-parity.md),
[generation-provenance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md),
[platform-and-tooling-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/platform-and-tooling-parity.md),
and
[cutover-compatibility-and-acceptance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)
(FT-15.04 / forge-template ADR 0061) — all merged and closed with
`FT-EPIC-15`.

**This contract is not the cutover.** No `create-forge` release named here
exists yet. Until [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)
implements it, the default `new` path stays direct-Copier with a bundled
registry, the engine stays the optional `engine` extra reachable only through
the hidden `new --engine-preview` flag, and
[`docs/cli-conventions.md`](cli-conventions.md) remains authoritative for
actual behaviour.

## The default route and installation

1. **The engine becomes the default `new` path.** `create-forge new "<name>"`
   with no route flag constructs a
   [ProjectSpec](https://github.com/Sandsy09/forge-template/blob/main/docs/project-spec.md),
   discovers the catalogue, validates, renders in memory, and finalises to
   disk through the public `forge_template` facade — the path
   `--engine-preview` reaches today.

2. **`forge-template` becomes a required dependency.** It moves from the
   optional `engine` extra into `[project.dependencies]`. A plain
   `pip install create-forge` / `uvx create-forge` resolves the engine, so the
   default route works with no extra. The engine range still moves only by a
   deliberate, human-authored line crossing
   ([ADR 0012](adr/0012-engine-dependency-update-policy.md)); adopting the
   `>=0.5,<0.6` cutover line is
   [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)'s, not this
   contract's.

3. **`copier` becomes the optional `legacy` extra.**
   `pip install 'create-forge[legacy]'` adds it back for the explicit legacy
   route below. `copier` keeps its strict, bounded range and its Dependabot
   compatibility-line gate ([ADR 0012](adr/0012-engine-dependency-update-policy.md),
   [ADR 0038](adr/0038-dependency-floor-review.md),
   [ADR 0039](adr/0039-copier-cache-diagnostics.md)) — the extra changes how it
   is installed, not how it is governed.

4. **`runner.py` stays the one module that touches Copier's Python API**, and
   `engine.py` stays the one module that imports `forge_template`
   ([ADR 0013](adr/0013-projectspec-construction-boundary.md)). The cutover
   makes `engine.py` reachable from the default path; it does not widen the
   set of modules that import the engine, and `compat.py` stays engine-free so
   `doctor` can still report the range without importing anything.

## The explicit `--legacy` route

5. **`--legacy` selects direct Copier.** A visible flag on `new`. Without it,
   `new` uses the engine. `--legacy` generates from the bundled registry
   (`src/create_forge/templates.toml`) through `runner.py`, exactly as the
   pre-cutover default `new` does — the
   [`forge-template` direct-Copier path is retained and not deprecated by the
   cutover](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md),
   so this route is a genuine, supported path, not a stub.

6. **The Copier-only options require `--legacy`.** `--template`,
   `--template-url` and `--ref` are valid only alongside `--legacy` and are an
   error without it — the mirror of today's rule that they are rejected *with*
   `--engine-preview`. `--template-url` keeps its source validation, its
   code-execution warning, and its confirmation-unless-`--yes` gate
   ([ADR 0036](adr/0036-template-source-credentials.md)); `--ref` keeps
   selecting a template tag. Neither is removed — this contract supersedes
   [ADR 0011](adr/0011-engine-source-and-version-resolution.md) on its
   "no dual direct-Copier path afterward" clause only.

7. **`--legacy` is the shared route name.**
   [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156) uses the
   same `--legacy` name for `update` dispatch; the routing rules for `update`
   (engine-native versus Copier, and how a project's recorded metadata selects
   between them) are that issue's to decide, not this one's.

8. **`--legacy` without the `legacy` extra fails closed.** If `copier` is not
   importable, `new --legacy` exits `3` (see
   [Exit statuses](#exit-statuses)) naming
   `pip install 'create-forge[legacy]'` as the remedy, before any prompt or
   destination write. It never falls through to the engine.

## `list`

9. **`list` prints the discovered engine catalogue.** Grouped by kind —
   archetypes, then capabilities, then platforms — each row showing the
   descriptor's `id`, `name` and `description`, built only from
   `discover_components()`. `create-forge` reads no component resource and
   names no component id of its own
   ([component discovery contract](component-discovery.md);
   `tests/test_archetype_parity.py`'s AST guard).

10. **`list --legacy` prints the bundled Copier registry** — the pre-cutover
    `list` output (id, name, description, status, default marker). It is the
    only place the registry is listed after the cutover.

## `doctor`

11. **`doctor` negotiates against the real engine.** It calls
    `get_engine_info()` and populates the diagnostics fields that are `null`
    today:
    [`docs/engine-resolution.md`](engine-resolution.md)'s
    `integration.projectspec_protocol.detected`, the component-manifest
    protocol tuple, and `metadata_version`. A package, protocol or
    `metadata_version` mismatch is a failed check — `doctor` reports it and
    exits `1`, the same rule the writable-cache probe already follows.

12. **`doctor` stays offline and side-effect-free.** No network call, no
    destination write, no render. `get_engine_info()` and
    `discover_components()` are both side-effect-free and callable before a
    destination exists
    ([cutover-compatibility-and-acceptance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)),
    which is what makes this safe. `engine.py` gains the call; `compat.py`
    stays engine-free.

13. **The diagnostics table shifts, additively where it can.**
    `integration.copier` becomes `null` when the `legacy` extra is absent.
    `integration.line` takes an engine-flavoured identifier of the form
    `v<major>.<minor>.x-engine`; the concrete value is
    [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)'s, reviewed
    against `pyproject.toml` by the existing
    `test_diagnostic_integration_line_matches_package_release_line` guard.
    `integration.engine_package` becomes a required field rather than a
    "`null` if the extra isn't installed" one. Every other field keeps its
    name and meaning.

## Generic component selection

14. **The five hidden selection flags become the visible primary surface**,
    names unchanged: `--archetype`, `--capability`, `--no-capabilities`,
    `--platform`, `--no-platforms`, `--component-option ID.OPTION=VALUE`. They
    lose the `"Development-only: "` help prefix and the exit-`1`
    *requires `--engine-preview`* rejection. Every rule in the
    [component selection contract](component-selection.md) — owner-qualified
    option syntax, the absent-versus-explicitly-empty encoding, deterministic
    prompt order, client-versus-engine validation ownership — carries over
    verbatim; only the flags' visibility changes.

15. **Nothing is pre-selected that the user did not choose.** In the
    interactive capability and platform multi-selects, only components the
    selected archetype's own discovered `requires` marks are pre-checked, and
    those are locked, annotated `(required by <archetype-id>)`, and confirmed
    rather than mutated — exactly as
    [ADR 0028](adr/0028-discovery-driven-component-selection.md) already
    implements. `create-forge` ships no curated "recommended" set and no
    component-id allowlist. This matches the provider's stated default profile,
    which
    [selects no capability or platform, keeping the engine's current output the
    floor](https://github.com/Sandsy09/forge-template/blob/main/docs/platform-and-tooling-parity.md).

16. **A required platform option with no default is a hard failure under
    `--yes`.** The `github` platform declares one required `organisation`
    option with no default
    ([platform-and-tooling-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/platform-and-tooling-parity.md)).
    Selecting `github` non-interactively without supplying
    `--component-option github.organisation=<value>` reaches the engine's own
    `validate` rejection, translated through `engine.explain` with the flag
    hint — never a synthesised default.

## Answer precedence

17. **Precedence is unchanged from
    [`docs/cli-conventions.md`](cli-conventions.md).** Config
    (`config.toml` then `FORGE_*`) pre-fills a prompt but never suppresses it;
    the positional name and `--data key=value` are explicit presets that
    suppress the matching prompt; a value the CLI does not ask for falls to
    engine defaults (`ProjectSpec` and engine validation, where Copier's
    `defaults=True` used to sit).

18. **`--data` presets ProjectSpec identity answers only** —
    `project_name`, `project_description`, `license` — the three answers
    `prompts.ask_project_answers` collects. A component option is set only
    through `--component-option ID.OPTION=VALUE`.

19. **The legacy `--data build_backend` / `--data versioning` →
    `packaging_mode` mapping is retired at the cutover.** It survives today
    only as a pre-cutover `--engine-preview` compatibility shim
    ([ADR 0019](adr/0019-cli-archetype-parity-review.md),
    [ADR 0025](adr/0025-engine-native-prompt-flow.md),
    [ADR 0029](adr/0029-per-component-option-collection.md)); the engine-default
    surface is `--component-option library.packaging_mode=<value>`.

20. **Ordinary configuration can never redirect an executable source.**
    `config.toml` and `FORGE_*` gain no component-option, source, engine,
    range or protocol field. `UserConfig`'s `extra="forbid"` turns an attempt
    to add one into a validation error
    (`tests/test_config.py::test_config_cannot_redirect_the_template_source`),
    exactly as [ADR 0011](adr/0011-engine-source-and-version-resolution.md)
    requires and this contract keeps.

## Interactive cancellation and non-interactive requirements

21. **Cancelling any prompt exits `130` with nothing written.** Ctrl-C /
    Ctrl-D at the archetype prompt, a capability or platform multi-select, a
    project answer, a component-option prompt, or the `--template-url`
    confirmation on the legacy route — all leave the destination untouched, as
    [`docs/cli-conventions.md`](cli-conventions.md)'s cancellation rule already
    requires. Update-flow cancellation, dry-run and rollback are
    [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156)'s.

22. **`--yes` disables prompts and requires a project name and an archetype.**
    The engine declares no default archetype, so `--yes` without `--archetype`
    is rejected outright, naming the available ids — the pre-cutover
    `--engine-preview` rule, now on the default path. Resolved config values
    and explicit presets still apply; unasked values use engine defaults.

23. **A missing TTY is not `--yes`.** Reaching a required prompt with no
    terminal to ask on and no `--yes` fails with exit `1` and guidance naming
    the flag that would have supplied the answer (`--archetype`,
    `--component-option`, …). A CI job never silently receives engine defaults
    it did not request.

24. **Interactive and non-interactive invocations converge.** After answer
    collection, equivalent resolved inputs produce the same `ProjectSpec`,
    selection, destination and dry-run setting on both routes, per
    [`docs/cli-conventions.md`](cli-conventions.md)'s parity rule.

## `--engine-source` / `--engine-ref`

The names [ADR 0011](adr/0011-engine-source-and-version-resolution.md)
reserved. They select which **engine distribution** provides `forge_template`;
they never name a Copier template or a component resource.

25. **They provision an isolated ephemeral environment.**
    `--engine-source <local-path|vcs-url>` (with optional `--engine-ref <ref>`,
    an error on its own) is installed with `uv` into a throwaway environment,
    and the whole generation runs against that engine. The installed engine is
    never imported, shadowed or modified. There is no in-process `sys.path`
    injection.

26. **Source validation is `--template-url`'s.** HTTP(S) user-info, SSH URL
    passwords, URL queries and fragments, malformed authorities and control
    characters are rejected with exit `1`
    ([ADR 0036](adr/0036-template-source-credentials.md)); ordinary SSH
    usernames, SCP-style sources and local paths are accepted. Errors identify
    the affected field without echoing its value.

27. **The code-execution warning is unconditional; `--yes` skips only the
    confirmation.** `--engine-source` runs code from a source the user
    supplied, outside the reviewed release. The warning always prints; without
    `--yes` it asks for confirmation (declining exits `130`); with `--yes` it
    prints the warning and proceeds.

28. **The resolved engine passes the same compatibility check.** Package,
    ProjectSpec-protocol, component-manifest-protocol and `metadata_version`
    negotiation runs against the provisioned engine before any discovery,
    render, task execution or destination write, and fails closed with exit
    `3` on a mismatch — no fallback to the installed engine, to Copier, or to
    the bundled registry.

29. **An `--engine-source` render is not update-eligible.** It writes no
    `.forge/generation.json` (the metadata file CF-16.02 /
    [ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md)
    fixed), because that document fixes `provider.distribution` to
    `"forge-template"` and admits no source URL, path or VCS ref as a value
    ([generation-provenance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md)).
    The post-generation message says so plainly, mirroring today's
    `--engine-preview` "create-forge update does not apply" line. CF-16.02
    confirmed no degraded-mode record is written for a non-default source
    either.

30. **`--engine-source` combines with `--legacy` as an error.** The override
    is an engine-package selector; it has no meaning on the Copier route,
    where `--template-url` is the equivalent escape hatch.

## Exit statuses

The [`docs/cli-conventions.md`](cli-conventions.md) exit-status table stays
authoritative. The cutover changes two rows:

| Status | Cutover meaning |
| --- | --- |
| `1` | Unchanged in kind. Now also covers a missing project name or archetype under `--yes` on the default route, and a required prompt reached with no TTY and no `--yes`. |
| `3` | **Widens by one sentence.** Today: an installed or overridden engine, or its ProjectSpec protocol, outside the supported range. After the cutover: also an engine that cannot be imported at all, an out-of-range component-manifest protocol or `metadata_version`, and `--legacy` without the `legacy` extra installed. One status means "the required generator is missing or unusable", still distinct from every other failure and still with no silent fallback. |

`2` (Typer usage errors, including a malformed `--component-option`) and `130`
(cancellation) are unchanged.

## Post-generation messaging

31. **One client-owned success panel, on both routes.** `create-forge` owns
    the post-generation next-steps text — the parity inventory assigns
    `_message_after_copy` to CF-16.01, "client UX and error presentation"
    ([engine-default-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/engine-default-parity.md)).
    The panel is today's `cli._report_created` shape: the project name and
    destination, the `cd` line, the check command
    (`uv run --locked poe check`), and one line about update eligibility —
    `Pull later changes with: create-forge update` for an engine or Copier
    render, the not-eligible line for an `--engine-source` render.

32. **The legacy route additionally prints the template's own text.** On
    `--legacy`, `copier.yml`'s `_message_after_copy` is shown as well, since
    that route runs Copier and the template author's message is part of it.
    The engine route has no equivalent template-authored hook.

## Deprecation sequencing

This contract fixes the **order** and the **rule**. The concrete releases and
windows are CF-16.03's, in the
[engine-default cutover acceptance contract](engine-cutover-acceptance.md)
([ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md)): the
cutover is `create-forge 0.4.0`, and any later-retired visible surface carries
a deprecation warning naming its replacement for at least 90 days and at least
one further tagged `create-forge` release — expressed relative to publication,
never as a calendar date.

33. **The direct-Copier route is not deprecated.** `--legacy`, `--template`,
    `--template-url`, `--ref`, the bundled registry and `create-forge update`
    against a Copier project all stay supported. The provider guarantees
    `template/`, `copier.yml` and `copier update` remain live
    ([cutover-compatibility-and-acceptance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)),
    so retiring the client's entry point to them is not on this roadmap.

34. **`--engine-preview` is removed in the cutover release, with no window.**
    It is hidden, absent from `--help`, and documented development-only, so it
    has no compatibility promise to honour. The release that makes the engine
    the default makes `--engine-preview` meaningless, and it is removed there —
    an unknown option, exit `2`.

35. **The rule for a visible surface.** Any visible flag or behaviour this
    contract removes or repoints later carries a deprecation warning for at
    least one further tagged `create-forge` release before removal, and the
    warning names the replacement. A hidden, development-only flag may be
    removed in the release that makes it meaningless.

## What this contract does not decide

- The engine range adoption (`>=0.5,<0.6`), the lock refresh, and the
  implementation of every rule above —
  [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158),
  [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159),
  [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160).
- `update` dispatch, the generation-metadata file (`.forge/generation.json`),
  the merge and conflict policy, dry-run, cancellation, rollback, and the
  `new` Git/hook lifecycle for the engine path — decided by CF-16.02
  ([ADR 0041](adr/0041-engine-project-lifecycle-and-update-dispatch.md),
  canonical [engine project lifecycle contract](engine-project-lifecycle.md)),
  built by
  [CF-18.03](https://github.com/Sandsy09/create-forge/issues/160) /
  [CF-18.04](https://github.com/Sandsy09/create-forge/issues/161).
- Legacy Copier-project preservation and the transition handling for projects
  scaffolded through the old `--engine-preview` —
  [CF-18.05](https://github.com/Sandsy09/create-forge/issues/162).
- The concrete cutover version number (`create-forge 0.4.0`), the supported
  OS / Python / install-mode matrix, the support and deprecation windows, the
  cross-repository acceptance matrix and the release gates — decided by CF-16.03
  ([ADR 0042](adr/0042-engine-cutover-acceptance-and-support-policy.md),
  canonical [engine-default cutover acceptance contract](engine-cutover-acceptance.md)).
- Any `forge-template` change. Provider manifests, composition, generated
  content and in-memory validation stay in `forge-template`
  (**CF-ROADMAP-01-EX-01**); this contract adds no archetype
  (**CF-ROADMAP-01-EX-02**) and no remote registry or plugin mechanism
  (**CF-ROADMAP-01-EX-03**).

## Executable examples

Until the cutover ships, the contract is guarded rather than characterised:

- [`tests/test_engine_default_contract.py`](../tests/test_engine_default_contract.py)
  derives what it can from the live pre-cutover CLI — `--engine-preview` and
  the five selection flags still hidden, the exit-`3` row still documented
  once, `forge-template` still an optional extra — and carries tripwires that
  fail deliberately when
  [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) /
  [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) land, so the
  implementation cannot ship without bringing this document back into step.
  It also asserts
  [ADR 0040](adr/0040-engine-default-selection-and-source-resolution.md) names
  its `CF-ROADMAP-01-EX-*` obligations literally.
- [`tests/test_engine_contract.py`](../tests/test_engine_contract.py)'s
  link-audit guard keeps this document reachable from `CLAUDE.md`,
  `CONTRIBUTING.md` and [`docs/cli-conventions.md`](cli-conventions.md).

When the cutover implements a rule above, move it from this contract's
"decided" voice into `docs/cli-conventions.md`'s "in force" voice and add its
characterization test in the same pull request.
