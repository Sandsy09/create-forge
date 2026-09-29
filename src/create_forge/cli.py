"""Command line interface for create-forge."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from create_forge.commands import _output
from create_forge.commands import catalogue as _catalogue_command
from create_forge.commands import config as _config_command
from create_forge.commands import doctor as _doctor_command
from create_forge.commands import new as _new_command
from create_forge.commands import selection as _selection
from create_forge.commands import update as _update_command
from create_forge.sources import SourceError, validate_source

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


@app.command("new")
def new(  # noqa: PLR0913, PLR0917 - a CLI entry point's options are its public surface; one parameter per --flag is unavoidable, and --engine-source's own validation and dispatch (ADR 0044) add one more early-exit branch each
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
    flags = _selection.ComponentFlags(
        capabilities=_selection._normalise_kind_flag(
            capability, none_flag=no_capabilities
        ),
        platforms=_selection._normalise_kind_flag(platform, none_flag=no_platforms),
        options=_parse_component_options(component_option or []),
    )

    _new_command.new(
        template_id=template_id,
        path=path,
        preset=preset,
        yes=yes,
        template_url=template_url,
        ref=ref,
        dry_run=dry_run,
        legacy=legacy,
        archetype=archetype,
        flags=flags,
        engine_source=engine_source,
        engine_ref=engine_ref,
    )


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
