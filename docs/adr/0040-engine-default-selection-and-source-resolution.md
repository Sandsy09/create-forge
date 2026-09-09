# 40. Define engine-default selection and source-resolution UX

## Status

Accepted

## Context

[ADR 0010](0010-public-engine-integration-contract.md) accepted a versioned
public `forge-template` engine as `create-forge`'s integration target, and
every engine ADR since has named the same unfinished step: the *cutover*, in
which the engine replaces direct Copier as the default `new` path. ADR 0010
left it "a separate, still-unfiled decision";
[ADR 0011](0011-engine-source-and-version-resolution.md) specified the
`--engine-source` / `--engine-ref` override "for the coordinated cutover" but
shipped nothing; [ADR 0018](0018-pypi-distribution-and-the-first-engine-range.md)
and [ADR 0026](0026-adopt-the-0-4-engine-compatibility-line.md) moved the
engine range without performing the switch;
[ADR 0025](0025-engine-native-prompt-flow.md) and
[ADR 0027](0027-generic-component-selection-conventions.md) built the
engine-native prompt and selection surface but kept every flag hidden behind
`new --engine-preview`.

The provider side is now decided. `forge-template` Stage 15 merged four
accepted living contracts and closed `FT-EPIC-15`:
[engine-default-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/engine-default-parity.md)
(every default-Copier behaviour assigned to provider, client or exclusion),
[generation-provenance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md)
(the metadata that reproduces or updates a generated project),
[platform-and-tooling-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/platform-and-tooling-parity.md)
(one `github` platform, eight capabilities), and
[cutover-compatibility-and-acceptance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/cutover-compatibility-and-acceptance.md)
(forge-template ADR 0061; the cutover publishes `forge-template` `0.5.0`, the
direct-Copier path is retained and not deprecated, and the CLI default switch,
the explicit legacy route and any deprecation timeline are
`create-forge`'s to decide). That fourth contract names
[CF-16.01 / #155](https://github.com/Sandsy09/create-forge/issues/155)
explicitly as the owner of those decisions, and the parity inventory assigns
one row directly to it: `_message_after_copy`, "client UX and error
presentation".

Three provider facts constrain the answers. The direct-Copier path is
guaranteed live — `template/`, `copier.yml` and `copier update` all keep
working — so a legacy route this decision defines must genuinely function, not
be a deprecation stub, which contradicts ADR 0011's promise of "no dual
direct-Copier path afterward". The cutover line is `forge-template` `0.5.0`,
but widening the client bound is
[CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)'s, not this
decision's. And the generation-metadata document fixes
`provider.distribution` to `"forge-template"` and admits no source URL, path
or VCS ref, so a project generated through `--engine-source` cannot be
described by it — silence on that point is not viable.

This is a decision issue. It records the contract in
[`docs/engine-default-cli.md`](../engine-default-cli.md) and updates the
living contracts it touches. It changes no runtime code, moves no dependency,
bumps no version, and requires no `forge-template` change. Every implementing
step is an already-filed
[CF-EPIC-18](https://github.com/Sandsy09/create-forge/issues/153) child.

Its review obligations are **CF-ROADMAP-01-AC-01** (a living CLI contract
defines the default, the explicit legacy route, configuration precedence,
prompts, `--yes` requirements and the deprecation timeline — owned solely
here), **CF-ROADMAP-01-AC-02** (data still flows `create-forge → ProjectSpec →
forge-template render → create-forge finalisation`, no component semantics
copied downstream — shared with
[CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)),
**CF-ROADMAP-01-AC-04** (missing or incompatible providers, invalid selections
and render or finalise failures have stable statuses and never fall back to
Copier — shared with
[CF-18.06](https://github.com/Sandsy09/create-forge/issues/163)),
**CF-ROADMAP-01-EX-01** (no provider manifest, composition or
generated-content change), **CF-ROADMAP-01-EX-02** (no new archetype), and
**CF-ROADMAP-01-EX-03** (no remote plugin or registry system).

## Decision

1. **Make the `forge-template` engine the default `new` path, with the engine
   as a required dependency.** `create-forge new "<name>"` with no route flag
   constructs a ProjectSpec, discovers, validates, renders and finalises
   through the public `forge_template` facade — the path `--engine-preview`
   reaches today. `forge-template` moves from the optional `engine` extra into
   `[project.dependencies]`, so a plain `pip install create-forge` resolves
   it. `engine.py` stays the one module that imports it
   ([ADR 0013](0013-projectspec-construction-boundary.md)); `compat.py` stays
   engine-free so `doctor` still reports the range without an import.

2. **Move `copier` to an optional `legacy` extra, reached through a visible
   `--legacy` flag.** `pip install 'create-forge[legacy]'` adds Copier back;
   `create-forge new --legacy` generates from the bundled registry through
   `runner.py`, exactly as the pre-cutover default `new` does. `--template`,
   `--template-url` and `--ref` are valid only alongside `--legacy` and an
   error without it — the mirror of today's rejection of those flags *with*
   `--engine-preview`. `--legacy` without the extra installed fails closed
   with exit `3`, never falling through to the engine. `--legacy` is the same
   route name [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156)
   uses for `update` dispatch.

3. **Supersede ADR 0011's atomic-replacement clause only; retain
   `--template-url` and `--ref`.** They keep their source validation
   ([ADR 0036](0036-template-source-credentials.md)), code-execution warning
   and confirmation-unless-`--yes` gate, scoped to `--legacy`.
   `--engine-source` / `--engine-ref` are a new, orthogonal pair that selects
   the engine *distribution* — never a Copier template. ADR 0011's Status
   stays `Accepted`: its installed-dependency rule, its `--engine-source`
   interface, its exit-`3` reservation and its "configuration cannot redirect
   a source" guarantee all still hold. Only the sentence "there is no dual
   direct-Copier path afterward" is overturned, by the provider's own
   retention guarantee.

4. **Resolve `--engine-source` / `--engine-ref` into an isolated ephemeral
   environment.** The named local path or VCS URL, with an optional
   `--engine-ref`, is provisioned with `uv` into a throwaway environment and
   the whole generation runs against that engine; the installed engine is
   never imported, shadowed or modified. Source validation is
   `--template-url`'s. The code-execution warning always prints; `--yes` skips
   the confirmation but never the warning. The resolved engine passes the
   identical package / protocol / `metadata_version` compatibility check
   before any render or write, failing closed with exit `3` and no fallback.
   [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) implements
   this.

5. **Write no generation metadata for an `--engine-source` render, and say so.**
   The metadata document cannot name a non-`forge-template` provider
   ([generation-provenance.md](https://github.com/Sandsy09/forge-template/blob/main/docs/generation-provenance.md)),
   so an override render is not `create-forge update`-eligible and its
   post-generation message states that plainly — mirroring today's
   `--engine-preview` behaviour. Whether a non-default source ever earns a
   degraded-mode metadata record is
   [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156)'s.

6. **Make `doctor` negotiate against the real engine, offline.** It calls
   `get_engine_info()` and populates `projectspec_protocol.detected`, the
   component-manifest protocol tuple and `metadata_version`; a mismatch is a
   failed check and exits `1`. `integration.copier` becomes `null` when the
   `legacy` extra is absent; `integration.line` takes an identifier of the
   form `v<major>.<minor>.x-engine` whose concrete value is
   [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)'s, still
   reviewed against `pyproject.toml` by the existing diagnostic-line guard. No
   network call, no destination write.

7. **Make `list` print the discovered engine catalogue; `list --legacy` prints
   the registry.** `list` groups `discover_components()` descriptors by kind
   with each `id`, `name` and `description`, reading no component resource and
   naming no component id in shipped code. `list --legacy` is the pre-cutover
   registry table.

8. **Un-hide the five selection flags without renaming them.** `--archetype`,
   `--capability`, `--no-capabilities`, `--platform`, `--no-platforms` and
   `--component-option ID.OPTION=VALUE` lose the `"Development-only: "` prefix
   and the *requires `--engine-preview`* rejection. Every rule in
   [`docs/component-selection.md`](../component-selection.md) carries over
   unchanged. `--engine-preview` itself is removed in the cutover release with
   no deprecation window — it is hidden and development-only, so it has no
   compatibility promise; an unknown option afterward, exit `2`.

9. **Pre-select nothing the user did not choose.** The interactive capability
   and platform multi-selects open with only the archetype's own discovered
   `requires` pre-checked and locked, exactly as
   [ADR 0028](0028-discovery-driven-component-selection.md) implements.
   `create-forge` ships no curated recommended set and no component-id
   allowlist — matching the provider's stated default profile, which selects
   no capability or platform. A required option with no default, such as
   `github.organisation`, reaches the engine's own `validate` rejection under
   `--yes` rather than a synthesised value.

10. **Keep answer precedence unchanged, and retire the legacy `--data`
    mapping.** Config pre-fills but never suppresses; positional name and
    `--data` presets suppress the matching prompt; unasked values fall to
    engine defaults. `--data` presets only the ProjectSpec identity answers
    (`project_name`, `project_description`, `license`); a component option is
    set only through `--component-option`. The
    `build_backend` / `versioning` → `packaging_mode` `--data` shim
    ([ADR 0019](0019-cli-archetype-parity-review.md),
    [ADR 0029](0029-per-component-option-collection.md)) is removed at the
    cutover. `config.toml` and `FORGE_*` gain no component-option, source,
    engine, range or protocol field — `UserConfig`'s `extra="forbid"` keeps
    enforcing it.

11. **Require a project name and an archetype under `--yes`, and treat a
    missing TTY as not `--yes`.** `--yes` without `--archetype` is rejected
    naming the available ids. Reaching a required prompt with no terminal and
    no `--yes` fails with exit `1` and guidance naming the flag that supplies
    the answer; a non-interactive run never silently receives engine defaults.
    Cancelling any generation prompt, or the `--template-url` confirmation,
    exits `130` with nothing written; update-flow cancellation, dry-run and
    rollback are [CF-16.02](https://github.com/Sandsy09/create-forge/issues/156)'s.

12. **Widen exit `3` to the whole provider-availability class.** It already
    covers an installed or overridden engine, or its ProjectSpec protocol,
    outside the supported range. The cutover adds: an engine that cannot be
    imported at all, an out-of-range component-manifest protocol or
    `metadata_version`, and `--legacy` without the `legacy` extra. One status
    means "the required generator is missing or unusable", still with no
    silent fallback. `2` and `130` are unchanged.

13. **Own the post-generation message on both routes.** One client-owned
    success panel — today's `cli._report_created` shape: project name and
    destination, the `cd` line, the check command, and one update-eligibility
    line (the not-eligible line for an `--engine-source` render). The
    `--legacy` route additionally prints `copier.yml`'s own
    `_message_after_copy`. This closes the parity row
    [engine-default-parity.md](https://github.com/Sandsy09/forge-template/blob/main/docs/engine-default-parity.md)
    assigns to CF-16.01.

14. **Fix the deprecation rule and sequence here; leave the numbers to
    CF-16.03.** The direct-Copier route — `--legacy`, `--template`,
    `--template-url`, `--ref`, the bundled registry, `create-forge update`
    against a Copier project — is not deprecated at all, because the provider
    guarantees its target stays live. A visible flag or behaviour removed or
    repointed later carries a deprecation warning naming its replacement for
    at least one further tagged `create-forge` release before removal; a
    hidden development-only flag may be removed in the release that makes it
    meaningless. The concrete releases, windows and dates are
    [CF-16.03](https://github.com/Sandsy09/create-forge/issues/157)'s.

15. **Publish the contract as `docs/engine-default-cli.md`.** A new canonical
    living document in the idiom of
    [`docs/component-selection.md`](../component-selection.md).
    [`docs/cli-conventions.md`](../cli-conventions.md) gains a pointer section
    and keeps the authoritative exit-status table and pre-cutover behaviour;
    [`docs/engine-resolution.md`](../engine-resolution.md) records the
    `--engine-source` mechanism and the `doctor` change against its existing
    diagnostics table; [`docs/component-selection.md`](../component-selection.md)
    and [`docs/integration-contract.md`](../integration-contract.md) get the
    corrections this decision forces. No new issue is filed — every
    implementing step maps to an existing CF-EPIC-18 child.

## Consequences

- `docs/engine-default-cli.md` is added and linked from `CLAUDE.md`,
  `CONTRIBUTING.md`, and `docs/cli-conventions.md`;
  `tests/test_engine_contract.py` gains a link-audit guard copying the
  existing ones.
- `tests/test_engine_default_contract.py` is added: derived assertions against
  the live pre-cutover CLI, plus tripwires that fail deliberately when
  [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158) and
  [CF-18.02](https://github.com/Sandsy09/create-forge/issues/159) land —
  `forge-template` still an optional extra, `copier` still required with no
  `legacy` extra, `compat.INTEGRATION_LINE` still ending `-copier`, `new()`
  with no `--legacy` / `--engine-source` / `--engine-ref` parameter, `doctor`
  still reporting `projectspec_protocol.detected` as `null`. It also asserts
  this record names `CF-ROADMAP-01-EX-01`, `-EX-02` and `-EX-03` literally.
- ADR 0011 is partially superseded in fact, not by an edit. Its Status stays
  `Accepted`; ADRs are immutable
  ([ADR 0001](0001-record-architecture-decisions.md)), and this record is what
  documents the one overturned clause — the same treatment
  [ADR 0019](0019-cli-archetype-parity-review.md) gave ADR 0017.
- `docs/cli-conventions.md`, `docs/engine-resolution.md`,
  `docs/component-selection.md` and `docs/integration-contract.md` are updated
  to point at the new contract and to replace their "future, unfiled" cutover
  language with "Stage 16 contract, not yet implemented". The
  `integration-contract.md` compatibility table is untouched — no range moves
  here.
- `CF-16.01`'s three acceptance bullets, its four `CF-ROADMAP-01` review
  obligations and the `_message_after_copy` parity row are all satisfied by
  the new ADR and contract; `CF-16.02` is unblocked.
- The cutover this contract describes is still unbuilt. This ADR performs no
  dependency move, no version bump, no CLI code change, no `forge-template`
  change, and no release — [CF-18.01](https://github.com/Sandsy09/create-forge/issues/158)
  onward do that, and until they land the default `new` path stays
  direct-Copier.
