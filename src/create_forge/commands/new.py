"""`new` -- legacy, default-engine, and `--engine-source` orchestration.

`cli.py`'s thin `new()` wrapper keeps every flag-contradiction check and the
raw `--data`/`--component-option` parsing (they're pure, unconditional, and
proven order-safe -- see docs/cli-command-map.md's `new` section, "Why
cli.py's new() wrapper parses eagerly"), then makes one call into `new()`
below with the parsed inputs.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.panel import Panel
from rich.text import Text

from create_forge import compat
from create_forge.commands import _legacy, _output
from create_forge.commands import selection as _selection
from create_forge.compat import ENGINE_DISTRIBUTION, SUPPORTED_ENGINE_RANGE
from create_forge.config import UserConfig, config_path, load_config
from create_forge.prompts import PromptAbortedError, ask_all, choose_template, slugify
from create_forge.registry import load_registry
from create_forge.sources import display_source
from create_forge.spec import build_spec_payload
from create_forge.staging import (
    DestinationConflictError,
    StagingError,
    ensure_available,
)

if TYPE_CHECKING:
    from create_forge.models import Registry, Template
    from create_forge.runner import ScaffoldRequest


def new(  # noqa: PLR0913 - one parameter per new()'s own distinct input, mirroring the Typer command's own justification
    *,
    template_id: str | None,
    path: Path | None,
    preset: dict[str, object],
    yes: bool,
    template_url: str | None,
    ref: str | None,
    dry_run: bool,
    legacy: bool,
    archetype: str | None,
    flags: _selection.ComponentFlags,
    engine_source: str | None,
    engine_ref: str | None,
) -> None:
    """Create a new project, once every flag-shape check has already passed."""
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


def _run_engine(  # noqa: PLR0912, PLR0913, PLR0915 - one parameter per new()'s own distinct input, a linear discover->select->collect->build->finalise orchestration (see new()'s own justification), and one added branch printing CF-18.03's lifecycle warnings
    preset: dict[str, object],
    cfg_answers: dict[str, object],
    path: Path | None,
    archetype: str | None,
    flags: _selection.ComponentFlags,
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

    descriptor, selection = _selection._resolve_engine_selection(
        catalogue, archetype, flags, yes=yes
    )

    _selection._validate_component_option_owners(catalogue, selection, flags.options)
    selected = catalogue.selected(selection)

    project_answers, collected_options = _selection._collect_engine_answers(
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
        hint = _selection._missing_requirement_hint(catalogue, descriptor, selection)
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
    flags: _selection.ComponentFlags,
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
        descriptor, selection = _selection._resolve_engine_selection(
            catalogue, archetype, flags, yes=yes
        )
        _selection._validate_component_option_owners(
            catalogue, selection, flags.options
        )
        selected = catalogue.selected(selection)

        project_answers, collected_options = _selection._collect_engine_answers(
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
            hint = _selection._missing_requirement_hint(
                catalogue, descriptor, selection
            )
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
