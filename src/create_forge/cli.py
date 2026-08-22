"""Command line interface for create-forge."""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from create_forge.config import config_path, env_overrides, load_config, write_example
from create_forge.prompts import PromptAborted, ask_all, choose_template, slugify
from create_forge.registry import load_registry
from create_forge.runner import ScaffoldError, ScaffoldRequest, scaffold, update

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


def _version() -> str:
    try:
        return version("create-forge")
    except PackageNotFoundError:  # pragma: no cover - editable installs
        return "unknown"


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


@app.callback()
def main(
    _version_flag: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=lambda v: (console.print(_version()), raise_exit()) if v else None,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """create-forge."""


def raise_exit() -> None:  # noqa: D103 - trivial; folded into the #4 cleanup
    raise typer.Exit


@app.command("new")
def new(  # noqa: PLR0913, PLR0912, PLR0915 - a CLI entry point legitimately has many options and branches
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
) -> None:
    """Create a new project."""
    registry = load_registry()
    preset = _parse_data(data or [])

    if name:
        preset.setdefault("project_name", name)

    try:
        config = load_config()
    except ValueError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    cfg_answers = config.as_answers()

    # --- resolve config's preferred template, if it names one ----------------
    try:
        preferred_id = (
            registry.get(config.default_template).id
            if config.default_template
            else registry.default_template
        )
    except KeyError as exc:
        err.print(f"[red]{config_path()} sets default_template: {exc.args[0]}[/red]")
        raise typer.Exit(1) from exc

    # --- pick the template ---------------------------------------------------
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
    except PromptAborted:
        raise typer.Exit(130) from None

    if template.status == "deprecated":
        err.print(
            f"[yellow]{template.id} is deprecated. "
            f"Use {template.deprecated_in_favour_of} instead.[/yellow]"
        )

    # --- collect answers -----------------------------------------------------
    if yes:
        if "project_name" not in preset:
            err.print("[red]--yes requires a project name.[/red]")
            raise typer.Exit(1)
        answers = {**cfg_answers, **preset}
    else:
        try:
            answers = {
                **cfg_answers,
                **ask_all(template, preset=preset, defaults=cfg_answers),
            }
        except PromptAborted:
            err.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(130) from None

    # --- resolve destination -------------------------------------------------
    slug = slugify(str(answers["project_name"]))
    dst = (path or Path.cwd() / slug).resolve()

    src = template_url or str(template.url)
    if template_url:
        err.print(
            Panel(
                f"Scaffolding from [bold]{template_url}[/bold]\n"
                "Template code will be executed. Only continue if you trust it.",
                title="[yellow]Third-party template[/yellow]",
                border_style="yellow",
            )
        )
        if not yes and not typer.confirm("Continue?", default=False):
            raise typer.Exit(130)

    # --- scaffold ------------------------------------------------------------
    try:
        with console.status(f"Scaffolding {slug}…"):
            scaffold(
                ScaffoldRequest(
                    src=src, dst=dst, data=answers, vcs_ref=ref, dry_run=dry_run
                )
            )
    except ScaffoldError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if dry_run:
        console.print("[dim]Dry run — nothing written.[/dim]")
        return

    console.print(
        Panel(
            f"[bold]{answers['project_name']}[/bold] created at [dim]{dst}[/dim]\n\n"
            f"  cd {dst.name}\n"
            "  uv run poe check\n\n"
            "[dim]Pull later template changes with: uvx create-forge update[/dim]",
            border_style="green",
        )
    )


@app.command("list")
def list_templates() -> None:
    """Show the available templates."""
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


@app.command("update")
def update_project(
    project: Annotated[Path, typer.Argument(help="Project directory.")] = Path(),
    ref: Annotated[
        str | None, typer.Option("--ref", help="Target version. Defaults to latest.")
    ] = None,
) -> None:
    """Pull template changes into an existing project."""
    try:
        with console.status("Updating…"):
            update(project.resolve(), vcs_ref=ref)
    except ScaffoldError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    console.print(
        "[green]Updated.[/green] Review the diff before committing — "
        "conflicts are marked inline."
    )


@app.command("doctor")
def doctor() -> None:
    """Check that the environment can scaffold and update projects."""
    ok = True

    table = Table(box=None, pad_edge=False)
    table.add_column("")
    table.add_column("Check")
    table.add_column("Detail", style="dim")

    def row(passed: bool, label: str, detail: str) -> None:
        nonlocal ok
        ok = ok and passed
        table.add_row("[green]✓[/]" if passed else "[red]✗[/]", label, detail)

    py = sys.version_info
    row(py >= (3, 11), "Python 3.11+", f"{py.major}.{py.minor}.{py.micro}")

    for tool, why in (
        ("git", "required to clone templates"),
        ("uv", "required by generated projects"),
    ):
        found = shutil.which(tool)
        row(bool(found), tool, found or f"not on PATH — {why}")

    if shutil.which("git"):
        name = _git_config("user.name")
        email = _git_config("user.email")
        row(
            bool(name and email),
            "git identity",
            f"{name} <{email}>"
            if name and email
            else "unset — scaffolding cannot commit",
        )

    try:
        registry = load_registry()
        row(True, "registry", f"{len(registry.templates)} template(s)")
    except RuntimeError as exc:
        row(False, "registry", str(exc).splitlines()[0])

    try:
        config = load_config()
        keys = (
            ", ".join(sorted(config.model_dump(exclude_none=True))) or "no values set"
        )
        row(True, "config", f"{config_path()} — {keys}")
    except ValueError as exc:
        row(False, "config", str(exc).splitlines()[0])

    console.print(table)
    if not ok:
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
