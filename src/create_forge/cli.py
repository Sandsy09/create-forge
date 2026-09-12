"""Command line interface for create-forge."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from create_forge.compat import (
    ENGINE_DISTRIBUTION,
    INTEGRATION_LINE,
    SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS,
    SUPPORTED_ENGINE_RANGE,
    SUPPORTED_GENERATION_METADATA_VERSIONS,
    SUPPORTED_PROJECTSPEC_PROTOCOLS,
)
from create_forge.config import (
    UserConfig,
    config_path,
    env_overrides,
    load_config,
    write_example,
)
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
console = Console()
err = Console(stderr=True)

config_app = typer.Typer(
    name="config",
    help="Inspect or initialise your create-forge configuration.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")


def _dist_version(name: str) -> str:
    """Installed version of a distribution, or "unknown" if it can't be found.

    Editable installs of `create-forge` itself hit the fallback in normal
    development; a distribution genuinely not being installed (e.g. `copier`
    in some hypothetical stripped environment) hits it too.
    """
    try:
        return version(name)
    except PackageNotFoundError:  # pragma: no cover - editable installs
        return "unknown"


def _optional_dist_version(name: str) -> str | None:
    """Installed version of an optional distribution, or `None` if absent.

    Distinct from `_dist_version`: `create-forge` always depends on `name`
    there, so "unknown" signals a broken environment. Here `name` is either
    the optional `legacy` extra's `copier` -- not installed is the normal,
    expected default -- or `forge-template`/`uv`, both required since ADR
    0040 (CF-18.01), where a genuine absence signals a broken install.
    docs/engine-resolution.md's diagnostics contract documents
    `integration.copier`/`integration.engine_package` as `null` for either
    case, never the string "unknown".
    """
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def _version() -> str:
    return _dist_version("create-forge")


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
        console.print(_version())
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


def _load_config_or_exit() -> UserConfig:
    """Load user config, exiting with a plain-language error if it is malformed."""
    try:
        return load_config()
    except ValueError as exc:
        err.print(f"[red]{exc}[/red]")
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
        err.print(f"[red]{config_path()} sets default_template: {exc.args[0]}[/red]")
        raise typer.Exit(1) from exc

    try:
        if template_id:
            template = registry.get(template_id)
        elif yes:
            template = registry.get(preferred_id)
        else:
            template = choose_template(registry.selectable, preferred_id)
    except KeyError as exc:
        err.print(f"[red]{exc.args[0]}[/red]")
        raise typer.Exit(1) from exc
    except PromptAbortedError:
        raise typer.Exit(130) from None

    if template.status == "deprecated":
        err.print(
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
            err.print("[red]--yes requires a project name.[/red]")
            raise typer.Exit(1)
        return {**cfg_answers, **preset}

    try:
        return {
            **cfg_answers,
            **ask_all(template, preset=preset, defaults=cfg_answers),
        }
    except PromptAbortedError:
        err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None


def _confirm_third_party(template_url: str | None, *, yes: bool) -> None:
    """Warn and, unless --yes, ask for confirmation before running foreign code."""
    if not template_url:
        return
    err.print(
        Panel(
            Text.assemble(
                "Scaffolding from ",
                (display_source(template_url), "bold"),
                "\nTemplate code will be executed. Only continue if you trust it.",
            ),
            title="[yellow]Third-party template[/yellow]",
            border_style="yellow",
        )
    )
    if not yes and not typer.confirm("Continue?", default=False):
        raise typer.Exit(130)


def _ensure_legacy_available() -> None:
    """Import `create_forge.runner`, failing closed if `copier` is absent.

    ADR 0040 decision 2 (CF-18.01) moves `copier` from a required dependency
    to the optional `legacy` extra: `runner.py` imports it at module scope
    (invariant 4), so this is now the lazy, guarded import -- reached only
    from `--legacy` and `update`, mirroring the shape `engine`/`pipeline`'s
    import had before the cutover. Decision 12 widens exit `3`'s
    provider-availability class to cover exactly this: a missing generator,
    not a usage error, so callers exit `3` rather than raising a bare
    `ImportError` traceback. Callers reached only after this succeeds import
    `create_forge.runner`'s names directly -- the module is already cached in
    `sys.modules`, so that second import is free.
    """
    try:
        import create_forge.runner  # noqa: F401, PLC0415
    except ImportError:
        err.print(
            "[red]The legacy Copier route isn't installed.[/red] Run "
            "`pip install 'create-forge[legacy]'` (or `uv sync --all-extras` "
            "in a create-forge checkout) to use --legacy."
        )
        raise typer.Exit(3) from None


def _run_scaffold(request: ScaffoldRequest, slug: str) -> None:
    """Scaffold, translating a ScaffoldError into a clean exit.

    Only reached after `_ensure_legacy_available` has already succeeded.
    """
    from create_forge.runner import ScaffoldError, scaffold  # noqa: PLC0415

    try:
        with console.status(f"Scaffolding {slug}…"):
            scaffold(request)
    except ScaffoldError as exc:
        err.print(f"[red]{exc}[/red]")
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
            err.print(
                f"[red]Unknown {_flag_name(kind)} {component_id!r}. "
                f"Available: {valid or 'none'}[/red]"
            )
            raise typer.Exit(1)
        if actual is not kind:
            err.print(
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
        err.print("\n[dim]Cancelled.[/dim]")
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
            err.print(
                f"[red]Unknown --component-option component {owner!r}. "
                f"Available: {available}[/red]"
            )
            raise typer.Exit(1)
        if owner not in selected:
            err.print(
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
            err.print(
                f"[red]Unknown archetype {archetype!r}. Available: "
                f"{', '.join(sorted(by_id))}[/red]"
            )
            raise typer.Exit(1)
        return by_id[archetype], True

    if yes:
        err.print(
            "[red]--yes requires --archetype. "
            f"Available: {', '.join(sorted(by_id))}[/red]"
        )
        raise typer.Exit(1)

    try:
        chosen = choose_archetype(archetypes)
    except PromptAbortedError:
        err.print("\n[dim]Cancelled.[/dim]")
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
            err.print("[red]--yes requires a project name.[/red]")
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
        err.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(130) from None

    return project_answers, component_options


def _run_engine(  # noqa: PLR0913, PLR0915 - one parameter per new()'s own distinct input, and a linear discover->select->collect->build->finalise orchestration; see new()'s own justification
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
            err.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc

    try:
        # `engine` is imported directly here (rather than accessed as
        # `pipeline.engine`) so mypy's strict implicit-reexport check has a
        # real, direct import to type against.
        from create_forge import engine, pipeline  # noqa: PLC0415
    except ImportError:
        err.print(
            "[red]forge-template is not installed.[/red] create-forge "
            f"requires {ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}; "
            "reinstall create-forge to restore it."
        )
        raise typer.Exit(3) from None

    try:
        catalogue = pipeline.discover_catalogue()
    except engine.EngineCompatibilityError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(3) from exc
    except engine.ForgeEngineError as exc:
        err.print(f"[red]{engine.explain(exc)}[/red]")
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
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    try:
        request = pipeline.build_generation_request(
            project_answers,
            selection=selection,
            component_options=component_options,
            catalogue=catalogue,
        )
    except engine.EngineCompatibilityError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(3) from exc
    except engine.ForgeEngineError as exc:
        lines = [engine.explain(exc)]
        hint = _missing_requirement_hint(catalogue, descriptor, selection)
        if hint:
            lines.append(hint)
        message = "\n".join(lines)
        err.print(f"[red]{message}[/red]")
        raise typer.Exit(1) from exc

    if dry_run:
        for file in request.rendered.files:
            console.print(f"[dim]would write[/dim] {file.target}")
        console.print("[dim]Dry run — nothing written.[/dim]")
        return

    try:
        pipeline.finalise_generation_request(request, dst)
    except StagingError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    _report_created(project_answers["project_name"], dst, updatable=False)


def _report_created(project_name: object, dst: Path, *, updatable: bool = True) -> None:
    """Print the one client-owned success panel, on either route.

    ADR 0040 decision 13: the same shape regardless of whether `new` took the
    default engine path or `--legacy`'s Copier path -- project name,
    destination, the `cd` line, the check command, and one update-eligibility
    line. The `--legacy` route additionally prints Copier's own
    `_message_after_copy` (via `runner.scaffold`/Copier itself); the engine
    route has no equivalent template-authored hook.
    """
    check_command = "uv run poe check" if updatable else "uv run --locked poe check"
    update_line = (
        "[dim]Pull later changes with: create-forge update[/dim]"
        if updatable
        else "[dim]Not yet update-eligible -- create-forge update does not "
        "apply to this project.[/dim]"
    )
    console.print(
        Panel(
            f"[bold]{project_name}[/bold] created at [dim]{dst}[/dim]\n\n"
            f"  cd {dst.name}\n"
            f"  {check_command}\n\n"
            f"{update_line}",
            border_style="green",
        )
    )


@app.command("new")
def new(  # noqa: PLR0913, PLR0917 - a CLI entry point's options are its public surface; one parameter per --flag is unavoidable
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
) -> None:
    """Create a new project."""
    if legacy and template_url is not None:
        try:
            validate_source(template_url)
        except SourceError as exc:
            err.print(str(exc), style="red", markup=False)
            raise typer.Exit(1) from None
    if archetype is not None and legacy:
        err.print("[red]--archetype and --legacy are contradictory.[/red]")
        raise typer.Exit(1)
    _any_component_flag = bool(
        capability or no_capabilities or platform or no_platforms or component_option
    )
    if _any_component_flag and legacy:
        err.print(
            "[red]--capability/--no-capabilities/--platform/--no-platforms/"
            "--component-option require the default engine path and have no "
            "effect with --legacy.[/red]"
        )
        raise typer.Exit(1)
    if capability and no_capabilities:
        err.print("[red]--capability and --no-capabilities are contradictory.[/red]")
        raise typer.Exit(1)
    if platform and no_platforms:
        err.print("[red]--platform and --no-platforms are contradictory.[/red]")
        raise typer.Exit(1)
    if not legacy and (template_id or template_url or ref):
        err.print(
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
        _ensure_legacy_available()
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
            console.print("[dim]Dry run — nothing written.[/dim]")
            return

        _report_created(answers["project_name"], dst)
        return

    flags = ComponentFlags(
        capabilities=_normalise_kind_flag(capability, none_flag=no_capabilities),
        platforms=_normalise_kind_flag(platform, none_flag=no_platforms),
        options=_parse_component_options(component_option or []),
    )
    _run_engine(preset, cfg_answers, path, archetype, flags, dry_run=dry_run, yes=yes)


def _list_legacy_registry() -> None:
    """Print the bundled Copier template registry (`list --legacy`)."""
    registry = load_registry()
    table = Table(box=None, pad_edge=False)
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Description", style="dim")
    table.add_column("Status")

    for template in registry.templates:
        marker = "" if template.status == "stable" else f"[yellow]{template.status}[/]"
        default = (
            " [dim](default)[/dim]" if template.id == registry.default_template else ""
        )
        table.add_row(
            template.id + default, template.name, template.description, marker
        )

    console.print(table)


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
    if legacy:
        _list_legacy_registry()
        return

    try:
        from create_forge import engine, pipeline  # noqa: PLC0415
    except ImportError:
        err.print(
            "[red]forge-template is not installed.[/red] create-forge "
            f"requires {ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}; "
            "reinstall create-forge to restore it."
        )
        raise typer.Exit(3) from None

    try:
        catalogue = pipeline.discover_catalogue()
    except engine.EngineCompatibilityError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(3) from exc
    except engine.ForgeEngineError as exc:
        err.print(f"[red]{engine.explain(exc)}[/red]")
        raise typer.Exit(1) from exc

    table = Table(box=None, pad_edge=False)
    table.add_column("ID", style="bold")
    table.add_column("Kind")
    table.add_column("Name")
    table.add_column("Description", style="dim")

    for kind in DESCRIPTOR_KIND:
        for descriptor in catalogue.of_kind(kind):
            table.add_row(
                descriptor.id,
                DESCRIPTOR_KIND[kind],
                descriptor.name,
                descriptor.description,
            )

    console.print(table)


@app.command("update")
def update_project(
    project: Annotated[Path, typer.Argument(help="Project directory.")] = Path(),
    ref: Annotated[
        str | None, typer.Option("--ref", help="Target version. Defaults to latest.")
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Validate the update without changing project files."
        ),
    ] = False,
) -> None:
    """Pull template changes into an existing project.

    Dispatches only to the Copier update route today -- engine-native update
    dispatch against the recorded generation-metadata file is CF-18.04's job.
    `copier` is the optional `legacy` extra now (ADR 0040 decision 2), so this
    command's own import of it is lazy and guarded, matching `new --legacy`'s.
    """
    _ensure_legacy_available()
    from create_forge.runner import ScaffoldError, update  # noqa: PLC0415

    try:
        status = "Checking update…" if dry_run else "Updating…"
        with console.status(status):
            update(project.resolve(), vcs_ref=ref, dry_run=dry_run)
    except ScaffoldError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if dry_run:
        console.print("[green]Dry run complete.[/green] No project files changed.")
        return

    console.print(
        "[green]Updated.[/green] Review the diff before committing — "
        "conflicts are marked inline."
    )


def _markers(target: Console) -> tuple[str, str]:
    """Return (pass, fail) markers the console's encoding can actually render.

    A Windows console on the cp1252 codepage -- the default outside Windows
    Terminal -- cannot encode the check-mark glyphs, and Rich lets the
    resulting UnicodeEncodeError propagate rather than degrading. `doctor`
    needs markers it knows will survive before it ever tries to print them.
    """
    try:
        "✓✗".encode(target.encoding)
    except (UnicodeEncodeError, LookupError):
        return "OK", "FAIL"
    return "✓", "✗"


@dataclass(frozen=True, slots=True)
class Check:
    """One row of `doctor` output.

    `informational` rows report a fact rather than a pass/fail condition (the
    installed Copier version, say) and never affect `doctor`'s exit status —
    only `passed=False` on a non-informational row does.
    """

    name: str
    passed: bool
    detail: str
    informational: bool = False


@dataclass(frozen=True, slots=True)
class Integration:
    """The active create-forge/forge-template integration line and its
    versions -- see docs/engine-resolution.md for what each field means and
    when it is populated. `engine_range` and every `*_supported` field are
    always populated: the declared range and supported protocols are fixed by
    this create-forge release, independent of the environment.
    `engine_package` is `None` only in a broken install -- `forge-template`
    is a required dependency since ADR 0040 (CF-18.01). `copier` is `None`
    when the optional `legacy` extra is absent. Since ADR 0040 decision 6,
    `doctor` negotiates against the real engine (`engine.get_info()`, which
    performs no compatibility check itself), so every `*_detected` field is
    populated whenever the engine is importable at all -- `None` only when it
    is not.
    """  # noqa: D205

    line: str
    copier: str | None
    engine_package: str | None
    engine_range: str
    projectspec_supported: str
    projectspec_detected: str | None
    component_manifest_supported: str
    component_manifest_detected: str | None
    metadata_version_supported: str
    metadata_version_detected: int | None
    template_source: str | None
    template_ref: str | None


@dataclass(frozen=True, slots=True)
class ConfigSummary:
    """Where config was read from and which keys it set."""

    path: str
    keys: list[str]


@dataclass(frozen=True, slots=True)
class CopierCache:
    """Copier's git-mirror cache location and whether create-forge could use
    it -- see docs/engine-resolution.md's diagnostics contract. `writable` is
    the only field that can fail a `doctor` check; the rest are facts.
    """  # noqa: D205

    path: str
    override: bool
    exists: bool
    writable: bool


@dataclass(frozen=True, slots=True)
class UvStatus:
    """The `uv` create-forge would actually run, and the one the `engine`
    extra declares -- distinct facts that can legitimately differ.
    """  # noqa: D205

    path: str | None
    version: str | None
    package: str | None


@dataclass(frozen=True, slots=True)
class Diagnostics:
    """Everything `doctor` reports, gathered once so the table and `--json`
    output can never disagree.
    """  # noqa: D205

    create_forge: str
    python: str
    platform: str
    integration: Integration
    config: ConfigSummary
    copier_cache: CopierCache | None
    uv: UvStatus
    checks: list[Check]

    @property
    def ok(self) -> bool:
        """Whether every non-informational check passed."""
        return all(check.passed for check in self.checks if not check.informational)


def _tooling_diagnostics(checks: list[Check]) -> tuple[CopierCache | None, UvStatus]:
    """Append the tooling rows and return the structured facts.

    The git / uv rows land in `checks` unconditionally; the Copier-cache rows
    only when `copier` -- the optional `legacy` extra since ADR 0040 decision
    2 -- is actually importable, reporting `None`/an informational row
    instead of raising when it is not (decision 6's "`integration.copier`
    becomes `null` when the `legacy` extra is absent", applied to the cache
    facts alongside it). The cache and uv facts `doctor --json` reports
    alongside the checks come back as dataclasses.
    """
    git_found = shutil.which("git")
    checks.append(
        Check(
            "git",
            bool(git_found),
            git_found or "not on PATH — required to clone templates",
        )
    )

    uv_found = shutil.which("uv")
    uv_version = _uv_version(uv_found)
    checks.append(
        Check(
            "uv",
            bool(uv_found),
            f"{uv_version} ({uv_found})"
            if uv_found and uv_version
            else uv_found or "not on PATH — required by generated projects",
        )
    )

    try:
        from create_forge.runner import (  # noqa: PLC0415
            cache_probe,
            copier_cache_location,
        )
    except ImportError:
        checks.append(
            Check(
                "copier cache",
                True,
                "not applicable — install with pip install 'create-forge[legacy]'",
                informational=True,
            )
        )
        return None, UvStatus(
            path=uv_found, version=uv_version, package=_optional_dist_version("uv")
        )

    cache = copier_cache_location()
    probe = cache_probe(cache)
    checks.append(
        Check(
            "copier cache",
            True,
            f"{cache.path} "
            + (
                "(COPIER_CACHE_DIR override)"
                if cache.overridden
                else "(default location)"
            ),
            informational=True,
        )
    )
    checks.append(
        Check(
            "copier cache writable",
            probe.writable,
            "writable"
            if probe.writable
            else "not writable — set COPIER_CACHE_DIR to a writable directory",
        )
    )

    return (
        CopierCache(
            path=str(cache.path),
            override=cache.overridden,
            exists=probe.exists,
            writable=probe.writable,
        ),
        UvStatus(
            path=uv_found,
            version=uv_version,
            package=_optional_dist_version("uv"),
        ),
    )


def _gather_diagnostics() -> Diagnostics:  # noqa: PLR0915 - one linear pass gathering every doctor fact and check, mirroring `_run_engine`'s own justification for a single unbroken flow rather than an arbitrary split
    """Run every doctor check and collect every reportable fact.

    `doctor` stays offline: it reports the registry's bundled template source
    but never resolves a ref, since that would mean a network call for what
    is meant to be a fast local health check. Since ADR 0040 decision 6,
    engine presence is checked via `importlib.metadata` (informational,
    matching every other tool row) *and* a real negotiation through
    `engine.get_info()`, which performs no compatibility check of its own --
    a protocol/`metadata_version` mismatch surfaces as one failed check row
    here rather than raising `EngineCompatibilityError` and crashing `doctor`
    outright. `*_detected` fields stay `None` only when the engine cannot be
    imported at all.
    """
    checks: list[Check] = []

    def check(passed: bool, name: str, detail: str) -> None:
        checks.append(Check(name, passed, detail))

    def info(name: str, detail: str) -> None:
        checks.append(Check(name, True, detail, informational=True))

    py = sys.version_info
    python_version = f"{py.major}.{py.minor}.{py.micro}"
    check(py >= (3, 11), "Python 3.11+", python_version)

    copier_cache, uv_status = _tooling_diagnostics(checks)

    if shutil.which("git"):
        name = _git_config("user.name")
        email = _git_config("user.email")
        check(
            bool(name and email),
            "git identity",
            f"{name} <{email}>"
            if name and email
            else "unset — scaffolding cannot commit",
        )

    registry: Registry | None = None
    try:
        registry = load_registry()
        check(True, "registry", f"{len(registry.templates)} template(s)")
    except RuntimeError as exc:
        check(False, "registry", str(exc).splitlines()[0])

    template_source: str | None = None
    if registry is not None:
        default = registry.get(registry.default_template)
        template_source = str(default.url)
        source_detail = (
            f"{template_source} (default: {registry.default_template}, "
            "ref: latest PEP 440 tag — resolved at scaffold time)"
        )
    else:
        source_detail = "unavailable — registry did not load"

    config_keys: list[str] = []
    try:
        config = load_config()
        config_keys = sorted(config.model_dump(exclude_none=True))
        keys_detail = ", ".join(config_keys) or "no values set"
        check(True, "config", f"{config_path()} — {keys_detail}")
    except ValueError as exc:
        check(False, "config", str(exc).splitlines()[0])

    engine_range = f"{ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}"
    engine_package = _optional_dist_version(ENGINE_DISTRIBUTION)
    copier_package = _optional_dist_version("copier")
    projectspec_supported = ",".join(str(p) for p in SUPPORTED_PROJECTSPEC_PROTOCOLS)
    manifest_supported = ",".join(
        str(p) for p in SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS
    )
    metadata_supported = ",".join(
        str(v) for v in SUPPORTED_GENERATION_METADATA_VERSIONS
    )

    info("create-forge", _dist_version("create-forge"))
    info(
        "copier",
        copier_package
        if copier_package is not None
        else "not installed — install with pip install 'create-forge[legacy]'",
    )
    info("template source", source_detail)
    info("integration line", INTEGRATION_LINE)
    check(
        engine_package is not None,
        "engine",
        f"{ENGINE_DISTRIBUTION} {engine_package} (supports {engine_range})"
        if engine_package is not None
        else f"not installed (supports {engine_range}) — reinstall create-forge",
    )

    projectspec_detected: str | None = None
    manifest_detected: str | None = None
    metadata_detected: int | None = None
    if engine_package is not None:
        try:
            from create_forge import engine as _engine  # noqa: PLC0415

            negotiated = _engine.get_info()
            projectspec_detected = ",".join(
                str(p) for p in negotiated.projectspec_protocols
            )
            manifest_detected = ",".join(
                str(p) for p in negotiated.component_manifest_protocols
            )
            metadata_detected = negotiated.metadata_version
            projectspec_ok = bool(
                set(negotiated.projectspec_protocols)
                & set(SUPPORTED_PROJECTSPEC_PROTOCOLS)
            )
            manifest_ok = bool(
                set(negotiated.component_manifest_protocols)
                & set(SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS)
            )
            metadata_ok = metadata_detected in SUPPORTED_GENERATION_METADATA_VERSIONS
        except Exception as exc:
            # doctor must never crash; a too-old engine may not even have
            # these attributes (e.g. `metadata_version` postdates 0.3.2) --
            # report whatever the engine raised or a stale shape produced as
            # one failed check row instead.
            check(False, "engine negotiation", str(exc).splitlines()[0])
        else:
            check(
                projectspec_ok and manifest_ok and metadata_ok,
                "engine negotiation",
                f"ProjectSpec {projectspec_detected}, component manifest "
                f"{manifest_detected}, metadata {metadata_detected}",
            )

    return Diagnostics(
        create_forge=_dist_version("create-forge"),
        python=python_version,
        platform=sys.platform,
        integration=Integration(
            line=INTEGRATION_LINE,
            copier=copier_package,
            engine_package=engine_package,
            engine_range=engine_range,
            projectspec_supported=projectspec_supported,
            projectspec_detected=projectspec_detected,
            component_manifest_supported=manifest_supported,
            component_manifest_detected=manifest_detected,
            metadata_version_supported=metadata_supported,
            metadata_version_detected=metadata_detected,
            template_source=template_source,
            template_ref=None,
        ),
        config=ConfigSummary(path=str(config_path()), keys=config_keys),
        copier_cache=copier_cache,
        uv=uv_status,
        checks=checks,
    )


def _uv_version(uv_path: str | None) -> str | None:
    """The version `uv --version` reports, or None when it can't be trusted.

    `uv --version` prints e.g. `uv 0.12.10`. Only a token that looks like a
    version is returned, so nothing arbitrary from the subprocess can reach
    `doctor`'s output.
    """
    if not uv_path:
        return None
    try:
        result = subprocess.run(  # noqa: S603
            [uv_path, "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
        return None
    match result.stdout.split():
        case [_, token, *_] if re.fullmatch(r"[0-9][0-9A-Za-z.+-]*", token):
            return token
        case _:
            return None


def _render_diagnostics_table(diagnostics: Diagnostics, target: Console) -> None:
    """Render `doctor`'s checks as the human-facing Rich table."""
    passed_marker, failed_marker = _markers(target)

    table = Table(box=None, pad_edge=False)
    table.add_column("")
    table.add_column("Check")
    table.add_column("Detail", style="dim")

    for entry in diagnostics.checks:
        if entry.informational:
            table.add_row("[dim]-[/]", entry.name, entry.detail)
            continue
        marker = passed_marker if entry.passed else failed_marker
        style = "green" if entry.passed else "red"
        table.add_row(f"[{style}]{marker}[/]", entry.name, entry.detail)

    target.print(table)


def _diagnostics_payload(diagnostics: Diagnostics) -> dict[str, object]:
    """The stable JSON shape `doctor --json` emits.

    Documented field-by-field in docs/engine-resolution.md's diagnostics
    contract -- new fields may be added, but existing ones keep their meaning.
    """
    integration = diagnostics.integration
    return {
        "create_forge": diagnostics.create_forge,
        "python": diagnostics.python,
        "platform": diagnostics.platform,
        "integration": {
            "line": integration.line,
            "copier": integration.copier,
            "engine_package": integration.engine_package,
            "engine_range": integration.engine_range,
            "projectspec_protocol": {
                "supported": integration.projectspec_supported,
                "detected": integration.projectspec_detected,
            },
            "component_manifest_protocol": {
                "supported": integration.component_manifest_supported,
                "detected": integration.component_manifest_detected,
            },
            "metadata_version": {
                "supported": integration.metadata_version_supported,
                "detected": integration.metadata_version_detected,
            },
            "template_source": integration.template_source,
            "template_ref": integration.template_ref,
        },
        "config": {"path": diagnostics.config.path, "keys": diagnostics.config.keys},
        "copier_cache": (
            {
                "path": diagnostics.copier_cache.path,
                "override": diagnostics.copier_cache.override,
                "exists": diagnostics.copier_cache.exists,
                "writable": diagnostics.copier_cache.writable,
            }
            if diagnostics.copier_cache is not None
            else None
        ),
        "uv": {
            "path": diagnostics.uv.path,
            "version": diagnostics.uv.version,
            "package": diagnostics.uv.package,
        },
        "checks": [
            {"name": c.name, "ok": c.passed, "detail": c.detail}
            for c in diagnostics.checks
            if not c.informational
        ],
        "ok": diagnostics.ok,
    }


@app.command("doctor")
def doctor(
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable diagnostics."),
    ] = False,
) -> None:
    """Check that the environment can scaffold and update projects."""
    diagnostics = _gather_diagnostics()

    if as_json:
        typer.echo(json.dumps(_diagnostics_payload(diagnostics), indent=2))
    else:
        _render_diagnostics_table(diagnostics, console)

    if not diagnostics.ok:
        raise typer.Exit(1)


@config_app.command("init")
def config_init() -> None:
    """Write a commented starter config file. Never overwrites an existing one."""
    target = config_path()
    existed = target.exists()
    write_example(target)
    if existed:
        console.print(f"[dim]{target} already exists — left untouched.[/dim]")
    else:
        console.print(f"[green]Wrote {target}.[/green] Edit it, then run `new` again.")


@config_app.command("show")
def config_show() -> None:
    """Print resolved configuration and where each value came from."""
    target = config_path()
    if not target.is_file():
        console.print(
            f"[dim]{target} does not exist.[/dim] Run `create-forge config init`."
        )

    try:
        config = load_config(target)
    except ValueError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    overridden = env_overrides()

    table = Table(box=None, pad_edge=False)
    table.add_column("Key")
    table.add_column("Value")
    table.add_column("Source", style="dim")

    for field, value in config.model_dump().items():
        if field in overridden:
            source = "environment"
        elif value is not None:
            source = "config file"
        else:
            source = "unset"
        table.add_row(field, str(value) if value is not None else "—", source)

    console.print(table)


def _git_config(key: str) -> str | None:
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "config", "--get", key],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):  # pragma: no cover
        return None
    return result.stdout.strip() or None
