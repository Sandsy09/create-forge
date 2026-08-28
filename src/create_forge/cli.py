"""Command line interface for create-forge."""

from __future__ import annotations

import json
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

from create_forge.config import (
    UserConfig,
    config_path,
    env_overrides,
    load_config,
    write_example,
)
from create_forge.prompts import PromptAbortedError, ask_all, choose_template, slugify
from create_forge.registry import load_registry
from create_forge.runner import ScaffoldError, ScaffoldRequest, scaffold, update
from create_forge.staging import (
    DestinationConflictError,
    StagingError,
    ensure_available,
)

if TYPE_CHECKING:
    from create_forge.models import Registry, Template

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
            f"Scaffolding from [bold]{template_url}[/bold]\n"
            "Template code will be executed. Only continue if you trust it.",
            title="[yellow]Third-party template[/yellow]",
            border_style="yellow",
        )
    )
    if not yes and not typer.confirm("Continue?", default=False):
        raise typer.Exit(130)


def _run_scaffold(request: ScaffoldRequest, slug: str) -> None:
    """Scaffold, translating a ScaffoldError into a clean exit."""
    try:
        with console.status(f"Scaffolding {slug}…"):
            scaffold(request)
    except ScaffoldError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc


def _run_engine_preview(
    answers: dict[str, object], archetype: str, dst: Path, *, dry_run: bool
) -> None:
    """The --engine-preview path: build, validate, render, stage, finalise.

    Stages and finalises into `dst` exactly like the Copier path, just
    through the engine (ADR 0015). `forge-template` stays a development-only
    dependency (ADR 0014), so the import is lazy and guarded: every other
    command, and `new` without this flag, must keep working with the
    dependency absent.
    """
    err.print(
        "[dim]--engine-preview is a development-only path (ADR 0014). "
        "forge-template's production catalogue is still empty, so this "
        "fails at validation today by design.[/dim]"
    )
    try:
        ensure_available(dst)
    except DestinationConflictError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    try:
        # Lazy by necessity, not style: forge-template is a development-only
        # dependency (ADR 0014), so this import must not run unless this
        # branch is actually reached. `engine` is imported directly here
        # (rather than accessed as `pipeline.engine`) so mypy's strict
        # implicit-reexport check has a real, direct import to type against.
        from create_forge import engine, pipeline  # noqa: PLC0415
    except ImportError:
        err.print(
            "[red]The engine dependency isn't installed.[/red] This is a "
            "development-only path -- run `uv sync --all-groups` in a "
            "create-forge checkout to use it."
        )
        raise typer.Exit(1) from None

    try:
        request = pipeline.build_generation_request(answers, archetype=archetype)
    except engine.EngineCompatibilityError as exc:
        err.print(f"[red]{exc}[/red]")
        raise typer.Exit(3) from exc
    except engine.ForgeEngineError as exc:
        err.print(f"[red]{engine.explain(exc)}[/red]")
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

    _report_created(answers["project_name"], dst, updatable=False)


def _report_created(project_name: object, dst: Path, *, updatable: bool = True) -> None:
    """Print the success panel once a project has actually been written."""
    update_line = (
        "[dim]Pull later template changes with: uvx create-forge update[/dim]"
        if updatable
        else "[dim]Built via --engine-preview -- create-forge update does not "
        "apply.[/dim]"
    )
    console.print(
        Panel(
            f"[bold]{project_name}[/bold] created at [dim]{dst}[/dim]\n\n"
            f"  cd {dst.name}\n"
            "  uv run poe check\n\n"
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
    engine_preview: Annotated[
        bool,
        typer.Option(
            "--engine-preview",
            hidden=True,
            help="Development-only: build via the public forge-template engine "
            "instead of Copier. No files are ever written by this path yet.",
        ),
    ] = False,
) -> None:
    """Create a new project."""
    registry = load_registry()
    preset = _parse_data(data or [])
    if name:
        preset.setdefault("project_name", name)

    config = _load_config_or_exit()
    cfg_answers = config.as_answers()

    template = _select_template(registry, config, template_id, yes=yes)
    answers = _collect_answers(template, preset, cfg_answers, yes=yes)

    slug = slugify(str(answers["project_name"]))
    dst = (path or Path.cwd() / slug).resolve()

    if engine_preview:
        _run_engine_preview(answers, template.id, dst, dry_run=dry_run)
        return

    src = template_url or str(template.url)

    _confirm_third_party(template_url, yes=yes)
    _run_scaffold(
        ScaffoldRequest(src=src, dst=dst, data=answers, vcs_ref=ref, dry_run=dry_run),
        slug,
    )

    if dry_run:
        console.print("[dim]Dry run — nothing written.[/dim]")
        return

    _report_created(answers["project_name"], dst)


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
    when it is populated. Every engine/ProjectSpec field is `None` under the
    v0.1.x direct-Copier line; there is no engine package to report yet.
    """  # noqa: D205

    line: str
    copier: str
    engine_package: str | None
    engine_range: str | None
    projectspec_supported: str | None
    projectspec_detected: str | None
    template_source: str | None
    template_ref: str | None


@dataclass(frozen=True, slots=True)
class ConfigSummary:
    """Where config was read from and which keys it set."""

    path: str
    keys: list[str]


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
    checks: list[Check]

    @property
    def ok(self) -> bool:
        """Whether every non-informational check passed."""
        return all(check.passed for check in self.checks if not check.informational)


def _gather_diagnostics() -> Diagnostics:
    """Run every doctor check and collect every reportable fact.

    `doctor` stays offline: it reports the registry's bundled template source
    but never resolves a ref, since that would mean a network call for what
    is meant to be a fast local health check.
    """
    checks: list[Check] = []

    def check(passed: bool, name: str, detail: str) -> None:
        checks.append(Check(name, passed, detail))

    def info(name: str, detail: str) -> None:
        checks.append(Check(name, True, detail, informational=True))

    py = sys.version_info
    python_version = f"{py.major}.{py.minor}.{py.micro}"
    check(py >= (3, 11), "Python 3.11+", python_version)

    for tool, why in (
        ("git", "required to clone templates"),
        ("uv", "required by generated projects"),
    ):
        found = shutil.which(tool)
        check(bool(found), tool, found or f"not on PATH — {why}")

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

    info("create-forge", _dist_version("create-forge"))
    info("copier", _dist_version("copier"))
    info("template source", source_detail)
    info("engine", "not installed — v0.1.x direct-Copier line")
    info("ProjectSpec protocol", "n/a — assigned at Stage 06")

    return Diagnostics(
        create_forge=_dist_version("create-forge"),
        python=python_version,
        platform=sys.platform,
        integration=Integration(
            line="v0.1.x-copier",
            copier=_dist_version("copier"),
            engine_package=None,
            engine_range=None,
            projectspec_supported=None,
            projectspec_detected=None,
            template_source=template_source,
            template_ref=None,
        ),
        config=ConfigSummary(path=str(config_path()), keys=config_keys),
        checks=checks,
    )


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
            "template_source": integration.template_source,
            "template_ref": integration.template_ref,
        },
        "config": {"path": diagnostics.config.path, "keys": diagnostics.config.keys},
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
