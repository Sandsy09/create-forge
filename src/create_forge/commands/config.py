"""`config init`/`config show`.

Distinct from the top-level `create_forge.config` module (which this reads
from) by package path -- `commands/config.py` never binds that module's own
name, only the specific names it needs, so there is no ambiguity at any call
site.
"""

from __future__ import annotations

import typer
from rich.table import Table

from create_forge.commands import _output
from create_forge.config import config_path, env_overrides, load_config, write_example


def config_init() -> None:
    """Write a commented starter config file. Never overwrites an existing one."""
    target = config_path()
    existed = target.exists()
    write_example(target)
    if existed:
        _output.console.print(f"[dim]{target} already exists — left untouched.[/dim]")
    else:
        _output.console.print(
            f"[green]Wrote {target}.[/green] Edit it, then run `new` again."
        )


def config_show() -> None:
    """Print resolved configuration and where each value came from."""
    target = config_path()
    if not target.is_file():
        _output.console.print(
            f"[dim]{target} does not exist.[/dim] Run `create-forge config init`."
        )

    try:
        config = load_config(target)
    except ValueError as exc:
        _output.err.print(f"[red]{exc}[/red]")
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

    _output.console.print(table)
