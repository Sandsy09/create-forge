"""`list` -- the discovered engine catalogue, or the legacy template registry."""

from __future__ import annotations

import typer
from rich.table import Table

from create_forge.commands import _output
from create_forge.compat import ENGINE_DISTRIBUTION, SUPPORTED_ENGINE_RANGE
from create_forge.registry import load_registry
from create_forge.spec import DESCRIPTOR_KIND


def _list_legacy_registry() -> None:
    """Print the bundled Copier template registry (`list --legacy`).

    `registry.py`'s own docstring calls a malformed bundled registry "a
    packaging bug, not a user error", but every other reader of it
    (`commands.doctor`, `cli._select_template`) still catches `RuntimeError`
    and prints a clean message rather than letting a raw traceback reach the
    user -- CLAUDE.md's own rule for every user-facing error. `list --legacy`
    was the one place that didn't (CF-25.01).
    """
    try:
        registry = load_registry()
    except RuntimeError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
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

    _output.console.print(table)


def list_templates(*, legacy: bool) -> None:
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

    _output.console.print(table)
