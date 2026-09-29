"""Command line interface for create-forge."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.panel import Panel
from rich.text import Text

from create_forge import compat
from create_forge.commands import _legacy, _output
from create_forge.commands import catalogue as _catalogue_command
from create_forge.commands import config as _config_command
from create_forge.commands import doctor as _doctor_command
from create_forge.commands import update as _update_command
from create_forge.compat import ENGINE_DISTRIBUTION, SUPPORTED_ENGINE_RANGE
from create_forge.config import UserConfig, config_path, load_config
from create_forge.prompts import (
    COMPONENT_PROMPTS,
    ArchetypeChoice,
    PromptAbortedError,
    ask_all,
    ask_project_answers,
    choose_archetype,
    choose_components,
    choose_template,
    resolve_component_options,
    slugify,
)
from create_forge.registry import load_registry
from create_forge.sources import SourceError, display_source, validate_source
from create_forge.spec import (
    DESCRIPTOR_KIND,
    SELECTABLE_KINDS,
    SelectionKind,
    SelectionRequest,
    build_spec_payload,
)
from create_forge.staging import (
    DestinationConflictError,
    StagingError,
    ensure_available,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from create_forge.models import Registry, Template
    from create_forge.pipeline import Catalogue
    from create_forge.runner import ScaffoldRequest

app = typer.Typer(
    name="create-forge",
    help="Scaffold modern Python projects from maintained templates.",
    no_args_is_help=True,
    add_completion=False,
)

config_app = typer.Typer(
    name="config",
    help="Inspect or initialise your create-forge configuration.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")


def _version() -> str:
    return _doctor_command._dist_version("create-forge")


def _parse_data(pairs: list[str]) -> dict[str, object]:
    """Turn `--data key=value` into answers, coercing obvious booleans."""
    parsed: dict[str, object] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            msg = f"--data expects key=value, got {pair!r}"
            raise typer.BadParameter(msg)
        lowered = value.lower()
        if lowered in {"true", "false"}:
            parsed[key] = lowered == "true"
        else:
            parsed[key] = value
    return parsed


def _parse_component_options(pairs: list[str]) -> dict[str, dict[str, str]]:
    """Turn `--component-option ID.OPTION=VALUE` into an owner-namespaced map.

    Split on the first `.` for the owner id, then the first `=` in the
    remainder for the option name; the value keeps any further `.`/`=`. The
    two identifier alphabets (a component id never contains `.`, an option
    name never contains `.` or `-`) make this unambiguous by construction. A
    repeated `ID.OPTION` takes the last value, exactly as a repeated `--data`
    key does (CF-13.04, ADR 0029). Malformed input -- no `.` or no `=` -- is a
    usage error, exit `2`, like malformed `--data`.
    """
    parsed: dict[str, dict[str, str]] = {}
    for pair in pairs:
        owner, dot, rest = pair.partition(".")
        name, sep, value = rest.partition("=")
        if not dot or not sep or not owner or not name:
            msg = f"--component-option expects ID.OPTION=VALUE, got {pair!r}"
            raise typer.BadParameter(msg)
        parsed.setdefault(owner, {})[name] = value
    return parsed


def _version_callback(show: bool) -> None:
    """Print the version and exit, if `--version` was passed."""
    if show:
        _output.console.print(_version())
        raise typer.Exit


@app.callback()
def main(
    _version_flag: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """create-forge."""
    _output._harden_console_encoding()


def _load_config_or_exit() -> UserConfig:
    """Load user config, exiting with a plain-language error if it is malformed."""
    try:
        return load_config()
    except ValueError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


def _select_template(
    registry: Registry, config: UserConfig, template_id: str | None, *, yes: bool
) -> Template:
    """Resolve which template to scaffold from --template, config, or a prompt.

    Also emits the deprecation warning, since it depends on the same
    resolution the caller needs the return value for.
    """
    try:
        preferred_id = (
            registry.get(config.default_template).id
            if config.default_template
            else registry.default_template
        )
    except KeyError as exc:
        _output.err.print(
            f"[red]{config_path()} sets default_template: {exc.args[0]}[/red]"
        )
        raise typer.Exit(1) from exc

    try:
        if template_id:
            template = registry.get(template_id)
        elif yes:
            template = registry.get(preferred_id)
        else:
            template = choose_template(registry.selectable, preferred_id)
    except KeyError as exc:
        _output.err.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(1) from exc
    except PromptAbortedError:
        raise typer.Exit(130) from None

    if template.status == "deprecated":
        _output.err.print(
            f"[yellow]{template.id} is deprecated. "
            f"Use {template.deprecated_in_favour_of} instead.[/yellow]"
        )

    return template


def _collect_answers(
    template: Template,
    preset: dict[str, object],
    cfg_answers: dict[str, object],
    *,
    yes: bool,
) -> dict[str, object]:
    """Gather answers from --yes/--data, or by prompting for anything missing."""
    if yes:
        if "project_name" not in preset:
            _output.err.print("[red]--yes requires a project name.[/red]")
            raise typer.Exit(1)
        return {**cfg_answers, **preset}

    try:
        return {
            **cfg_answers,
            **ask_all(template, preset=preset, defaults=cfg_answers),
        }
    except PromptAbortedError:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None


def _confirm_third_party(
    template_url: str | None,
    *,
    yes: bool,
    title: str = "[yellow]Third-party template[/yellow]",
    lead: str = "Scaffolding from ",
    detail: str = "\nTemplate code will be executed. Only continue if you trust it.",
) -> None:
    """Warn and, unless --yes, ask for confirmation before running foreign code.

    `title`/`lead`/`detail` default to the `--template-url` wording;
    `--engine-source` (ADR 0044) reuses this same warning-then-confirm shape
    with its own text -- rule 27's "the warning always prints; `--yes` skips
    only the confirmation" applies identically to both.
    """
    if not template_url:
        return
    _output.err.print(
        Panel(
            Text.assemble(lead, (display_source(template_url), "bold"), detail),
            title=title,
            border_style="yellow",
        )
    )
    if not yes and not typer.confirm("Continue?", default=False):
        raise typer.Exit(130)


def _run_scaffold(request: ScaffoldRequest, slug: str) -> None:
    """Scaffold, translating a ScaffoldError into a clean exit.

    Only reached after `_ensure_legacy_available` has already succeeded.
    """
    from create_forge.runner import ScaffoldError, scaffold  # noqa: PLC0415

    try:
        with _output.console.status(f"Scaffolding {slug}…"):
            scaffold(request)
    except ScaffoldError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


@dataclass(frozen=True, slots=True)
class ComponentFlags:
    """The engine `new` path's component-selection flags, normalised.

    `capabilities`/`platforms` are the *effective* value for one selectable
    kind: `tuple[str, ...]` from one or more `--capability`/`--platform`, `()`
    from `--no-capabilities`/`--no-platforms` (an explicit empty choice), and
    `None` when neither was given (absent -- resolve interactively or leave to
    a policy default). `new()` rejects a `--capability` + `--no-capabilities`
    contradiction before building this (CF-13.03, ADR 0028).

    `options` is the owner-namespaced `--component-option ID.OPTION=VALUE` map
    (CF-13.04, ADR 0029), empty when the flag was not given. A repeated
    `ID.OPTION` has already collapsed to its last value in `_parse_component_options`.
    """

    capabilities: tuple[str, ...] | None
    platforms: tuple[str, ...] | None
    options: Mapping[str, Mapping[str, str]]

    def for_kind(self, kind: SelectionKind) -> tuple[str, ...] | None:
        """The normalised flag value for one selectable kind."""
        if kind is SelectionKind.CAPABILITIES:
            return self.capabilities
        return self.platforms


def _normalise_kind_flag(
    values: list[str] | None, *, none_flag: bool
) -> tuple[str, ...] | None:
    """One `--capability`/`--platform` list + its `--no-*` bool → effective value."""
    if values:
        return tuple(values)
    return () if none_flag else None


def _flag_name(kind: SelectionKind) -> str:
    """The user-facing flag that selects one kind: `--capability` etc."""
    return f"--{DESCRIPTOR_KIND[kind]}"


def _validate_flag_ids(
    catalogue: Catalogue, kind: SelectionKind, ids: Sequence[str]
) -> tuple[str, ...]:
    """De-duplicate flag-supplied ids and reject unknown or wrong-kind ones.

    Shape-only, answerable from the descriptor list alone (ADR 0027): an id
    the catalogue does not contain, or one whose discovered kind is not
    `kind`. Everything semantic -- requirements, conflicts, option domains --
    stays engine-owned. Exits `1`, phrased like `_select_archetype`'s own
    unknown-archetype message.
    """
    seen: list[str] = []
    for component_id in ids:
        if component_id in seen:
            continue
        actual = catalogue.kind_of(component_id)
        if actual is None:
            valid = ", ".join(sorted(d.id for d in catalogue.of_kind(kind)))
            _output.err.print(
                f"[red]Unknown {_flag_name(kind)} {component_id!r}. "
                f"Available: {valid or 'none'}[/red]"
            )
            raise typer.Exit(1)
        if actual is not kind:
            _output.err.print(
                f"[red]{_flag_name(kind)} {component_id!r} is not a "
                f"{DESCRIPTOR_KIND[kind]} (it is the {DESCRIPTOR_KIND[actual]} "
                f"{component_id!r}).[/red]"
            )
            raise typer.Exit(1)
        seen.append(component_id)
    return tuple(seen)


def _resolve_kind(
    catalogue: Catalogue,
    descriptor: ArchetypeChoice,
    kind: SelectionKind,
    flag_value: tuple[str, ...] | None,
    *,
    yes: bool,
) -> tuple[tuple[str, ...], bool]:
    """Resolve one selectable kind to `(ids, explicit)` (CF-13.03, ADR 0028).

    Flag given → validated ids, explicit. No descriptors of this kind, or
    `--yes` with no flag → `((), False)` (absent; never prompted). Every
    descriptor required by the archetype → those ids, *not* explicit (no
    choice was offered, mirroring `_select_archetype`'s skip-when-one).
    Otherwise a multi-select with the required entries pre-locked → explicit,
    even when nothing extra is ticked.
    """
    if flag_value is not None:
        return _validate_flag_ids(catalogue, kind, flag_value), True

    available = catalogue.of_kind(kind)
    if not available:
        return (), False

    required = catalogue.required_ids(descriptor.id, kind)
    if all(d.id in set(required) for d in available):
        return required, False

    if yes:
        return (), False

    picked = choose_components(
        COMPONENT_PROMPTS[kind.value],
        available,
        required=required,
        required_by=descriptor.id,
    )
    return picked, True


def _resolve_selection(
    catalogue: Catalogue,
    descriptor: ArchetypeChoice,
    flags: ComponentFlags,
    *,
    archetype_explicit: bool,
    yes: bool,
) -> SelectionRequest:
    """Build the full `SelectionRequest` for the chosen archetype.

    Runs `_resolve_kind` for each selectable kind in tier order and threads
    each kind's own explicitness into `SelectionRequest.of` -- so a kind whose
    ids were selected without a choice being offered stays non-explicit
    (CF-13.03, ADR 0028).
    """
    resolved = {
        kind: _resolve_kind(catalogue, descriptor, kind, flags.for_kind(kind), yes=yes)
        for kind in SELECTABLE_KINDS
    }
    caps, caps_explicit = resolved[SelectionKind.CAPABILITIES]
    platforms, platforms_explicit = resolved[SelectionKind.PLATFORMS]
    return SelectionRequest.of(
        archetype=descriptor.id,
        archetype_explicit=archetype_explicit,
        capabilities=caps,
        platforms=platforms,
        capabilities_explicit=caps_explicit,
        platforms_explicit=platforms_explicit,
    )


def _resolve_engine_selection(
    catalogue: Catalogue,
    archetype: str | None,
    flags: ComponentFlags,
    *,
    yes: bool,
) -> tuple[ArchetypeChoice, SelectionRequest]:
    """Pick the archetype, then resolve capabilities and platforms around it.

    All component selection happens here, before any project answer is
    collected (ADR 0025's ordering, extended by ADR 0028). A cancelled
    multi-select exits `130` with nothing written.
    """
    descriptor, archetype_explicit = _select_archetype(
        catalogue.archetypes, archetype, yes=yes
    )
    try:
        selection = _resolve_selection(
            catalogue, descriptor, flags, archetype_explicit=archetype_explicit, yes=yes
        )
    except PromptAbortedError:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None
    return descriptor, selection


def _missing_requirement_hint(
    catalogue: Catalogue, descriptor: ArchetypeChoice, selection: SelectionRequest
) -> str:
    """Flag hints for direct requirements the selection still omits.

    The `--yes` half of ADR 0027's asymmetric required-component rule:
    `create-forge` adds nothing, but when the engine is about to reject a
    missing hard requirement, it says which flag supplies it. Empty when the
    selection is complete.
    """
    chosen = {*selection.capabilities, *selection.platforms}
    hints = [
        f"Add {_flag_name(kind)} {req_id}."
        for kind in SELECTABLE_KINDS
        for req_id in catalogue.required_ids(descriptor.id, kind)
        if req_id not in chosen
    ]
    return " ".join(hints)


def _validate_component_option_owners(
    catalogue: Catalogue,
    selection: SelectionRequest,
    options: Mapping[str, Mapping[str, str]],
) -> None:
    """Reject a `--component-option` owner that is unknown or unselected.

    Both checks are answerable from the discovered catalogue and the resolved
    selection alone (ADR 0027), and both exit `1` before any prompt or write.
    An option *name* the owner does not declare, a value outside `choices`, a
    wrong type, a missing `required` one -- all stay engine verdicts.
    """
    selected = {
        component_id
        for kind in DESCRIPTOR_KIND
        for component_id in selection.ids_for(kind)
    }
    for owner in options:
        if catalogue.kind_of(owner) is None:
            available = ", ".join(sorted(d.id for d in catalogue.descriptors))
            _output.err.print(
                f"[red]Unknown --component-option component {owner!r}. "
                f"Available: {available}[/red]"
            )
            raise typer.Exit(1)
        if owner not in selected:
            _output.err.print(
                f"[red]--component-option component {owner!r} is not selected. "
                f"Selected: {', '.join(sorted(selected))}[/red]"
            )
            raise typer.Exit(1)


def _select_archetype(
    archetypes: Sequence[ArchetypeChoice], archetype: str | None, *, yes: bool
) -> tuple[ArchetypeChoice, bool]:
    """Resolve which archetype to build: explicit, --yes, then a prompt.

    CF-08.02. Mirrors `_select_template`'s resolution shape for the Copier
    path, but
    with no config- or registry-supplied default: the engine declares no
    default archetype, and `templates.toml`'s `default_template` is a
    Copier-path concept the engine path deliberately does not inherit.

    Returns the chosen descriptor alongside whether the choice was explicit
    (CF-09.01, ADR 0022): `--archetype` and an actually-prompted answer both
    are; `choose_archetype`'s own skip-when-only-one-exists shortcut is not,
    since no alternative was ever offered and a policy default could
    legitimately still apply there. Returning the descriptor itself, not just
    its id, is what lets the caller prompt for its declared `options` (#91,
    ADR 0025) without a second discovery lookup.
    """
    by_id = {a.id: a for a in archetypes}

    if archetype is not None:
        if archetype not in by_id:
            _output.err.print(
                f"[red]Unknown archetype {archetype!r}. Available: "
                f"{', '.join(sorted(by_id))}[/red]"
            )
            raise typer.Exit(1)
        return by_id[archetype], True

    if yes:
        _output.err.print(
            "[red]--yes requires --archetype. "
            f"Available: {', '.join(sorted(by_id))}[/red]"
        )
        raise typer.Exit(1)

    try:
        chosen = choose_archetype(archetypes)
    except PromptAbortedError:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None
    # `choose_archetype` itself skips the prompt when there is exactly one
    # archetype (mirroring `choose_template`) -- no alternative was ever
    # offered, so that case is not an explicit choice.
    return chosen, len(archetypes) > 1


def _collect_engine_answers(  # noqa: PLR0913 - project answers plus per-component options need the archetype, the full selected set, both preset sources, config, and the yes switch
    descriptor: ArchetypeChoice,
    selected: Sequence[ArchetypeChoice],
    preset: dict[str, object],
    cfg_answers: dict[str, object],
    option_flags: Mapping[str, Mapping[str, str]],
    *,
    yes: bool,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    """Gather identity answers and every selected component's declared options.

    Collected from --yes/--data/--component-option, or by prompting (#91,
    ADR 0025; CF-13.04, ADR 0029). Mirrors `_collect_answers`'s shape.

    `preset` (from `--data`) is split by the *archetype's* own declared option
    names: a match is an archetype-option answer (precedence rule 2 -- an
    unqualified `--data` name never targets a capability), everything else is a
    project-identity answer, including keys with no ProjectSpec home at all
    (`github_org`) and the legacy `build_backend`/`versioning` pair
    `pipeline._resolved_component_options` still inspects.

    `option_flags` is the owner-qualified `--component-option` map (rule 1),
    layered over the archetype `--data` presets. `resolve_component_options`
    then walks `selected` in composition-tier order, collecting each declared
    option the namespace did not already supply -- prompting only when not
    `--yes`, and omitting a component whose namespace stays empty.
    """
    archetype_option_names = {option.name for option in descriptor.options}
    archetype_preset = {k: v for k, v in preset.items() if k in archetype_option_names}
    project_preset = {
        k: v for k, v in preset.items() if k not in archetype_option_names
    }

    presets: dict[str, Mapping[str, object]] = {}
    for owner, values in option_flags.items():
        presets[owner] = dict(values)
    if archetype_preset:
        presets[descriptor.id] = {
            **archetype_preset,
            **presets.get(descriptor.id, {}),
        }

    if yes:
        if "project_name" not in project_preset:
            _output.err.print("[red]--yes requires a project name.[/red]")
            raise typer.Exit(1)
        project_answers = {**cfg_answers, **project_preset}
        component_options = resolve_component_options(
            selected, presets=presets, prompt=False
        )
        return project_answers, component_options

    try:
        project_answers = {
            **cfg_answers,
            **ask_project_answers(preset=project_preset, defaults=cfg_answers),
        }
        component_options = resolve_component_options(
            selected, presets=presets, prompt=True
        )
    except PromptAbortedError:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None

    return project_answers, component_options


def _run_engine(  # noqa: PLR0912, PLR0913, PLR0915 - one parameter per new()'s own distinct input, a linear discover->select->collect->build->finalise orchestration (see new()'s own justification), and one added branch printing CF-18.03's lifecycle warnings
    preset: dict[str, object],
    cfg_answers: dict[str, object],
    path: Path | None,
    archetype: str | None,
    flags: ComponentFlags,
    *,
    dry_run: bool,
    yes: bool,
) -> None:
    """The default engine `new` path: discover, select, prompt, build, render.

    Stages and finalises exactly like the `--legacy` Copier path, just
    through the engine (ADR 0015). ADR 0040 (CF-18.01) made this the default
    architecture: `forge-template` is a required dependency, so a plain
    `pip install create-forge` / `uvx create-forge` always resolves it. The
    import here stays lazy and guarded even so -- a genuinely broken
    environment (the dependency failed to install, or was removed) fails
    closed at exit `3` rather than crashing with a raw traceback, matching
    ADR 0040 decision 12's widened provider-availability class.

    #91 / ADR 0025: this path reads no registry data at all. It discovers
    the component catalogue once, resolves which archetype to build and which
    capabilities/platforms to select alongside it (CF-13.03, ADR 0028), then
    prompts directly from every *selected* component's own declared
    `ComponentDescriptor.options` (CF-13.04, ADR 0029) instead of reusing
    `templates.toml`'s Library-shaped registry questions -- so `--archetype
    cli` asks nothing `library`-specific, and the destination is only known
    once a project name has been collected. Owner-qualified `--component-option`
    values are validated against the resolved selection first (an unknown or
    unselected owner exits `1` before any prompt). The one discovered
    `Catalogue` is threaded into `build_generation_request` so
    `engine.discover()` runs exactly once.

    An explicit `--path` is still checked for a conflict before the engine is
    imported at all, preserving that guarantee for the common case where the
    destination is already knowable; the final destination (which may
    instead be derived from an interactively-collected project name) is
    checked again immediately before any construction, validation, or render
    begins -- still before every side effect that writes anything.
    """
    if path is not None:
        try:
            ensure_available(path)
        except DestinationConflictError as exc:
            _output.err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

    try:
        # `engine` is imported directly here (rather than accessed as
        # `pipeline.engine`) so mypy's strict implicit-reexport check has a
        # real, direct import to type against.
        from create_forge import engine, pipeline  # noqa: PLC0415
    except ImportError:
        _output.err.print(
            "[red]forge-template is not installed.[/red] create-forge "
            f"requires {ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}; "
            "reinstall create-forge to restore it."
        )
        raise typer.Exit(3) from None

    try:
        catalogue = pipeline.discover_catalogue()
    except engine.EngineCompatibilityError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(3) from exc
    except engine.ForgeEngineError as exc:
        _output.err.print(f"[red]{engine.explain(exc)}[/red]")
        raise typer.Exit(1) from exc

    descriptor, selection = _resolve_engine_selection(
        catalogue, archetype, flags, yes=yes
    )

    _validate_component_option_owners(catalogue, selection, flags.options)
    selected = catalogue.selected(selection)

    project_answers, collected_options = _collect_engine_answers(
        descriptor, selected, preset, cfg_answers, flags.options, yes=yes
    )
    component_options = collected_options or None

    dst = (path or Path.cwd() / slugify(str(project_answers["project_name"]))).resolve()
    try:
        ensure_available(dst)
    except DestinationConflictError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    try:
        request = pipeline.build_generation_request(
            project_answers,
            selection=selection,
            component_options=component_options,
            catalogue=catalogue,
        )
    except engine.EngineCompatibilityError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(3) from exc
    except engine.ForgeEngineError as exc:
        lines = [engine.explain(exc)]
        hint = _missing_requirement_hint(catalogue, descriptor, selection)
        if hint:
            lines.append(hint)
        message = "\n".join(lines)
        _output.err.print(f"[red]{message}[/red]")
        raise typer.Exit(1) from exc

    if dry_run:
        for file in request.rendered.files:
            _output.console.print(f"[dim]would write[/dim] {file.target}")
        _output.console.print("[dim]Dry run — nothing written.[/dim]")
        return

    try:
        warnings = pipeline.finalise_generation_request(request, dst)
    except StagingError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    for warning in warnings:
        _output.err.print(f"[yellow]{warning}[/yellow]")
    _report_created(project_answers["project_name"], dst, updatable=True)


def _run_engine_source(  # noqa: PLR0912, PLR0913, PLR0915 - mirrors _run_engine's own justification: one parameter per new()'s distinct input, feeding an isolated provision->discover->select->collect->render->finalise orchestration with its own failure branch per stage
    preset: dict[str, object],
    cfg_answers: dict[str, object],
    path: Path | None,
    archetype: str | None,
    flags: ComponentFlags,
    *,
    source: str,
    ref: str | None,
    dry_run: bool,
    yes: bool,
) -> None:
    """The `--engine-source` override `new` path (ADR 0040 decision 4, ADR 0044).

    Provisions the named source into an isolated ephemeral environment with
    `uv` and runs the whole generation against it through an out-of-process
    worker (`engine_source.py`/`_engine_worker.py`) -- the installed engine is
    never imported, shadowed, or in-process `sys.path`-injected (rule 25).
    Component selection, project-answer collection, and destination
    resolution reuse the exact same helpers `_run_engine` calls for the
    default route, so interactive and non-interactive behaviour converges
    identically on both (rule 24); only how the catalogue is discovered and
    how the render is produced differ -- through `engine_source`'s worker
    protocol instead of the installed `forge_template` package.

    A render produced this way writes no generation-metadata document
    (rule 29): `_report_created` is told so via `engine_source=True` and
    prints the not-eligible line.
    """
    if path is not None:
        try:
            ensure_available(path)
        except DestinationConflictError as exc:
            _output.err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

    _confirm_third_party(
        source,
        yes=yes,
        title="[yellow]Engine source override[/yellow]",
        lead="Building from engine source ",
        detail="\nforge-template will be installed from this source and its "
        "code will be executed. Only continue if you trust it.",
    )

    try:
        from create_forge import engine_source, pipeline  # noqa: PLC0415
    except ImportError:
        _output.err.print(
            "[red]forge-template is not installed.[/red] create-forge "
            f"requires {ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}; "
            "reinstall create-forge to restore it."
        )
        raise typer.Exit(3) from None

    try:
        requirement = engine_source.build_requirement(source, ref)
    except engine_source.EngineSourceError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    with contextlib.ExitStack() as stack:
        try:
            # `provision()`'s own body -- two `uv` invocations -- can raise
            # `EngineSourceError` before ever yielding a runtime (CF-23.02:
            # observed reaching the user as a raw traceback, because a bare
            # `with engine_source.provision(...) as runtime:` has nothing
            # here to catch an `__enter__`-time failure). `ExitStack.
            # enter_context` still registers the cleanup once entry succeeds,
            # so a later failure inside the block still removes the
            # provisioned environment exactly as the `with` form would have.
            runtime = stack.enter_context(engine_source.provision(requirement))
        except engine_source.EngineSourceError as exc:
            _output.err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        try:
            engine_source.negotiate(runtime)
        except compat.EngineCompatibilityError as exc:
            _output.err.print(f"[red]{exc}[/red]")
            raise typer.Exit(3) from exc
        except engine_source.EngineSourceError as exc:
            _output.err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        try:
            descriptors = engine_source.discover(runtime)
        except engine_source.EngineSourceError as exc:
            _output.err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        catalogue = pipeline.Catalogue(descriptors)
        descriptor, selection = _resolve_engine_selection(
            catalogue, archetype, flags, yes=yes
        )
        _validate_component_option_owners(catalogue, selection, flags.options)
        selected = catalogue.selected(selection)

        project_answers, collected_options = _collect_engine_answers(
            descriptor, selected, preset, cfg_answers, flags.options, yes=yes
        )
        component_options = collected_options or None

        dst = (
            path or Path.cwd() / slugify(str(project_answers["project_name"]))
        ).resolve()
        try:
            ensure_available(dst)
        except DestinationConflictError as exc:
            _output.err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

        payload = build_spec_payload(
            project_answers,
            archetype=selection.archetype,
            capabilities=selection.capabilities,
            platforms=selection.platforms,
            component_options=component_options,
        )
        try:
            files = engine_source.render(runtime, payload)
        except engine_source.EngineSourceError as exc:
            lines = [str(exc)]
            hint = _missing_requirement_hint(catalogue, descriptor, selection)
            if hint:
                lines.append(hint)
            _output.err.print(f"[red]{chr(10).join(lines)}[/red]")
            raise typer.Exit(1) from exc

    if dry_run:
        for target, _content in files:
            _output.console.print(f"[dim]would write[/dim] {target}")
        _output.console.print("[dim]Dry run — nothing written.[/dim]")
        return

    try:
        warnings = pipeline.finalise_files(files, dst)
    except StagingError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    for warning in warnings:
        _output.err.print(f"[yellow]{warning}[/yellow]")
    _report_created(
        project_answers["project_name"], dst, updatable=False, engine_source=True
    )


def _report_created(
    project_name: object,
    dst: Path,
    *,
    updatable: bool = True,
    engine_source: bool = False,
) -> None:
    """Print the one client-owned success panel, on either route.

    ADR 0040 decision 13: the same shape regardless of whether `new` took the
    default engine path or `--legacy`'s Copier path -- project name,
    destination, the `cd` line, the check command, and one update-eligibility
    line. The `--legacy` route additionally prints Copier's own
    `_message_after_copy` (via `runner.scaffold`/Copier itself); the engine
    route has no equivalent template-authored hook.

    `engine_source=True` (ADR 0044) is its own not-eligible wording, distinct
    from the plain "not yet" line: an `--engine-source` render will never
    become update-eligible (it writes no generation-metadata document at
    all, rule 29), which is a different fact from "this route doesn't have
    engine-native update wired up yet."
    """
    check_command = "uv run poe check" if updatable else "uv run --locked poe check"
    if updatable:
        update_line = "[dim]Pull later changes with: create-forge update[/dim]"
    elif engine_source:
        update_line = (
            "[dim]Generated from --engine-source -- create-forge update does "
            "not apply to this project.[/dim]"
        )
    else:
        update_line = (
            "[dim]Not yet update-eligible -- create-forge update does not "
            "apply to this project.[/dim]"
        )
    _output.console.print(
        Panel(
            f"[bold]{project_name}[/bold] created at [dim]{dst}[/dim]\n\n"
            f"  cd {dst.name}\n"
            f"  {check_command}\n\n"
            f"{update_line}",
            border_style="green",
        )
    )


@app.command("new")
def new(  # noqa: PLR0912, PLR0913, PLR0915, PLR0917 - a CLI entry point's options are its public surface; one parameter per --flag is unavoidable, and --engine-source's own validation and dispatch (ADR 0044) add one more early-exit branch each
    name: Annotated[
        str | None,
        typer.Argument(help="Project name. Prompted for when omitted."),
    ] = None,
    template_id: Annotated[
        str | None,
        typer.Option("--template", "-t", help="Template to use."),
    ] = None,
    path: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Where to create the project."),
    ] = None,
    data: Annotated[
        list[str] | None,
        typer.Option("--data", "-d", help="Preset an answer: key=value. Repeatable."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip prompts; use template defaults."),
    ] = False,
    template_url: Annotated[
        str | None,
        typer.Option(
            "--template-url",
            help="Clone from a different template. Runs its code — only use "
            "sources you trust.",
        ),
    ] = None,
    ref: Annotated[
        str | None,
        typer.Option("--ref", help="Template version. Defaults to the latest tag."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be written, write nothing."),
    ] = False,
    legacy: Annotated[
        bool,
        typer.Option(
            "--legacy",
            help="Build via the bundled Copier template registry instead of "
            "the default forge-template engine. Requires the `legacy` extra "
            "(pip install 'create-forge[legacy]').",
        ),
    ] = False,
    archetype: Annotated[
        str | None,
        typer.Option("--archetype", help="The engine archetype to build."),
    ] = None,
    capability: Annotated[
        list[str] | None,
        typer.Option(
            "--capability", help="A discovered capability to select. Repeatable."
        ),
    ] = None,
    no_capabilities: Annotated[
        bool,
        typer.Option("--no-capabilities", help="Select no capabilities, explicitly."),
    ] = False,
    platform: Annotated[
        list[str] | None,
        typer.Option("--platform", help="A discovered platform to select. Repeatable."),
    ] = None,
    no_platforms: Annotated[
        bool,
        typer.Option("--no-platforms", help="Select no platforms, explicitly."),
    ] = False,
    component_option: Annotated[
        list[str] | None,
        typer.Option(
            "--component-option",
            help="Set a selected component's option, ID.OPTION=VALUE. Repeatable.",
        ),
    ] = None,
    engine_source: Annotated[
        str | None,
        typer.Option(
            "--engine-source",
            help="Build against a forge-template engine from this local path or "
            "VCS URL instead of the installed one. Provisions an isolated "
            "environment and runs its code — only use sources you trust. Not "
            "create-forge update-eligible.",
        ),
    ] = None,
    engine_ref: Annotated[
        str | None,
        typer.Option(
            "--engine-ref",
            help="A VCS revision for --engine-source. Requires --engine-source "
            "and a VCS (not local-path) source.",
        ),
    ] = None,
) -> None:
    """Create a new project."""
    if legacy and template_url is not None:
        try:
            validate_source(template_url)
        except SourceError as exc:
            _output.err.print(str(exc), style="red", markup=False)
            raise typer.Exit(1) from None
    if archetype is not None and legacy:
        _output.err.print("[red]--archetype and --legacy are contradictory.[/red]")
        raise typer.Exit(1)
    if engine_ref is not None and engine_source is None:
        _output.err.print("[red]--engine-ref requires --engine-source.[/red]")
        raise typer.Exit(1)
    if engine_source is not None and legacy:
        _output.err.print("[red]--engine-source and --legacy are contradictory.[/red]")
        raise typer.Exit(1)
    if engine_source is not None:
        try:
            validate_source(engine_source, origin="--engine-source")
        except SourceError as exc:
            _output.err.print(str(exc), style="red", markup=False)
            raise typer.Exit(1) from None
    _any_component_flag = bool(
        capability or no_capabilities or platform or no_platforms or component_option
    )
    if _any_component_flag and legacy:
        _output.err.print(
            "[red]--capability/--no-capabilities/--platform/--no-platforms/"
            "--component-option require the default engine path and have no "
            "effect with --legacy.[/red]"
        )
        raise typer.Exit(1)
    if capability and no_capabilities:
        _output.err.print(
            "[red]--capability and --no-capabilities are contradictory.[/red]"
        )
        raise typer.Exit(1)
    if platform and no_platforms:
        _output.err.print("[red]--platform and --no-platforms are contradictory.[/red]")
        raise typer.Exit(1)
    if not legacy and (template_id or template_url or ref):
        _output.err.print(
            "[red]--template/--template-url/--ref require --legacy and have "
            "no effect on the default engine path, which selects an archetype "
            "instead of a Copier template (ADR 0040).[/red]"
        )
        raise typer.Exit(1)

    preset = _parse_data(data or [])
    if name:
        preset.setdefault("project_name", name)

    config = _load_config_or_exit()
    cfg_answers = config.as_answers()

    if legacy:
        _legacy._ensure_legacy_available()
        from create_forge.runner import ScaffoldRequest  # noqa: PLC0415

        registry = load_registry()
        template = _select_template(registry, config, template_id, yes=yes)
        answers = _collect_answers(template, preset, cfg_answers, yes=yes)

        slug = slugify(str(answers["project_name"]))
        dst = (path or Path.cwd() / slug).resolve()

        src = template_url or str(template.url)

        _confirm_third_party(template_url, yes=yes)
        _run_scaffold(
            ScaffoldRequest(
                src=src, dst=dst, data=answers, vcs_ref=ref, dry_run=dry_run
            ),
            slug,
        )

        if dry_run:
            _output.console.print("[dim]Dry run — nothing written.[/dim]")
            return

        _report_created(answers["project_name"], dst)
        return

    flags = ComponentFlags(
        capabilities=_normalise_kind_flag(capability, none_flag=no_capabilities),
        platforms=_normalise_kind_flag(platform, none_flag=no_platforms),
        options=_parse_component_options(component_option or []),
    )
    if engine_source is not None:
        _run_engine_source(
            preset,
            cfg_answers,
            path,
            archetype,
            flags,
            source=engine_source,
            ref=engine_ref,
            dry_run=dry_run,
            yes=yes,
        )
        return
    _run_engine(preset, cfg_answers, path, archetype, flags, dry_run=dry_run, yes=yes)


@app.command("list")
def list_templates(
    legacy: Annotated[
        bool,
        typer.Option(
            "--legacy", help="List the bundled Copier template registry instead."
        ),
    ] = False,
) -> None:
    """Show the discovered engine catalogue, or the legacy template registry.

    ADR 0040 decisions 7/9 (CF-18.01): the default view is the engine's own
    discovered catalogue, grouped archetypes-then-capabilities-then-platforms
    and built only from `discover_components()` -- reading no component
    resource and naming no component id in shipped code. `list --legacy` is
    the pre-cutover registry table, the only place it is listed after the
    cutover.
    """
    _catalogue_command.list_templates(legacy=legacy)


@app.command("update")
def update_project(
    project: Annotated[Path, typer.Argument(help="Project directory.")] = Path(),
    ref: Annotated[
        str | None, typer.Option("--ref", help="Target version. Copier route only.")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Validate the update without changing project files."
        ),
    ] = False,
    legacy: Annotated[
        bool,
        typer.Option("--legacy", help="Force the direct-Copier update route."),
    ] = False,
    degraded: Annotated[
        bool,
        typer.Option(
            "--degraded",
            help=(
                "Allow a two-way update with no merge base when the recorded "
                "engine release is unavailable. Engine-native route only."
            ),
        ),
    ] = False,
) -> None:
    """Pull template changes into an existing project.

    Routes by file (ADR 0041 rule 7): a committed `.forge/generation.json`
    reaches the engine-native route below; `.copier-answers.yml` only reaches
    the direct-Copier route, unchanged; `--legacy` forces Copier even when
    both files are present; neither file exits `1` naming both routes.
    `copier` is the optional `legacy` extra (ADR 0040 decision 2), so its
    import stays lazy and guarded, reached only once the Copier route is
    actually selected. The direct-Copier route stays reachable even when the
    engine itself is unusable (ADR 0047 rule 3) -- a `.copier-answers.yml`
    project does not depend on the engine at all.
    """
    _update_command.update_project(
        project=project, ref=ref, dry_run=dry_run, legacy=legacy, degraded=degraded
    )


@app.command("doctor")
def doctor(
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable diagnostics."),
    ] = False,
) -> None:
    """Check that the environment can scaffold and update projects."""
    _doctor_command.doctor(as_json=as_json)


@config_app.command("init")
def config_init() -> None:
    """Write a commented starter config file. Never overwrites an existing one."""
    _config_command.config_init()


@config_app.command("show")
def config_show() -> None:
    """Print resolved configuration and where each value came from."""
    _config_command.config_show()
