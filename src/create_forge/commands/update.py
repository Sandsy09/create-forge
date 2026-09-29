"""`update` -- file-based routing, the direct-Copier route, the engine-native
route, and Git-state recovery printing.

Distinct from the existing engine-free `create_forge.update` module (routing
predicate, clean-tree check, merge/apply, recovery guidance) by package path
-- this module orchestrates that one, never the reverse, and the two are
never imported into each other by mistake since one lives under `commands/`.
"""  # noqa: D205

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.panel import Panel

from create_forge.commands import _legacy, _output
from create_forge.compat import ENGINE_DISTRIBUTION, SUPPORTED_ENGINE_RANGE
from create_forge.staging import StagingError

if TYPE_CHECKING:
    from create_forge import update as update_module


def update_project(
    project: Path, *, ref: str | None, dry_run: bool, legacy: bool, degraded: bool
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
    try:
        from create_forge import engine, update  # noqa: PLC0415
    except ImportError:
        _output.err.print(
            "[red]forge-template is not installed.[/red] create-forge "
            f"requires {ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}; "
            "reinstall create-forge to restore it."
        )
        raise typer.Exit(3) from None

    resolved = project.resolve()
    try:
        metadata_filename = engine.generation_metadata_target()
    except (ImportError, engine.EngineCompatibilityError):
        # ADR 0047 rule 3: the metadata filename is an engine-owned constant
        # an out-of-range engine may predate entirely (engine.py's own
        # docstring). A project that records Copier answers does not need it
        # -- fall back to the Copier route rather than failing every update
        # for a project the engine never touches.
        if (resolved / update.COPIER_ANSWERS_FILE).is_file():
            if degraded:
                _output.err.print(
                    "[red]--degraded applies only to the engine-native "
                    "update route.[/red]"
                )
                raise typer.Exit(1) from None
            _run_copier_update(resolved, ref=ref, dry_run=dry_run)
            return
        _output.err.print(
            "[red]The installed forge-template engine is unusable.[/red] "
            f"create-forge requires {ENGINE_DISTRIBUTION}{SUPPORTED_ENGINE_RANGE}; "
            "reinstall create-forge to restore it, or run `create-forge "
            "doctor` for details."
        )
        raise typer.Exit(3) from None

    try:
        route = update.route_for(
            resolved, metadata_filename=metadata_filename, legacy=legacy
        )
    except update.UpdateError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if route is update.Route.COPIER:
        if degraded:
            _output.err.print(
                "[red]--degraded applies only to the engine-native update route.[/red]"
            )
            raise typer.Exit(1)
        _run_copier_update(resolved, ref=ref, dry_run=dry_run)
        return

    if ref is not None:
        _output.err.print(
            "[red]--ref selects a Copier template revision and applies only "
            "to the --legacy route.[/red] The engine-native route always "
            "targets the installed forge-template release -- upgrade "
            "create-forge to move it forward."
        )
        raise typer.Exit(1)

    _run_engine_update(resolved, dry_run=dry_run, degraded=degraded)


def _run_copier_update(project: Path, *, ref: str | None, dry_run: bool) -> None:
    """The direct-Copier `update` route, unchanged from before CF-18.04."""
    from create_forge.update import COPIER_ANSWERS_FILE  # noqa: PLC0415

    _legacy._ensure_legacy_available(
        purpose="to update this project, which records Copier answers in "
        f"{COPIER_ANSWERS_FILE}"
    )
    from create_forge.runner import ScaffoldError  # noqa: PLC0415
    from create_forge.runner import update as copier_update  # noqa: PLC0415

    try:
        status = "Checking update…" if dry_run else "Updating…"
        with _output.console.status(status):
            copier_update(project, vcs_ref=ref, dry_run=dry_run)
    except ScaffoldError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if dry_run:
        _output.console.print(
            "[green]Dry run complete.[/green] No project files changed."
        )
        return

    _output.console.print(
        "[green]Updated.[/green] Review the diff before committing — "
        "conflicts are marked inline."
    )


def _confirm_degraded(reason: str) -> bool:
    """Rule 22: never automatic -- explains the lost merge base and asks.

    Non-interactive or closed stdin behaves as a decline, not a raw traceback.
    """
    _output.err.print(
        Panel(
            f"{reason}\n\n"
            "A degraded two-way update can proceed instead: it compares only "
            "the new render against the working tree, so it cannot tell a "
            "local edit from an old template default.",
            title="[yellow]Unavailable recorded release[/yellow]",
            border_style="yellow",
        )
    )
    try:
        return typer.confirm("Continue with a degraded update?", default=False)
    except typer.Abort:
        return False


def _print_dry_run_summary(outcome: update_module.UpdateOutcome) -> None:
    """Rule 16: a genuine per-target classification list.

    `unchanged` targets are summarised as a count rather than listed one by
    one.
    """
    unchanged = 0
    for result in outcome.results:
        if result.status == "unchanged":
            unchanged += 1
            continue
        marker = "CONFLICT" if result.status == "conflict" else result.status
        line = f"[dim]{result.classification:<9}[/dim] {marker:<10} {result.target}"
        _output.console.print(line)
    _output.console.print(f"[dim]{unchanged} unchanged target(s).[/dim]")


def _report_update_result(outcome: update_module.UpdateOutcome) -> None:
    """Rule 23: one client-owned message, plus a clean/conflicted count.

    A no-op update (rule 15) reports that nothing changed instead.
    """
    if outcome.changed == 0:
        _output.console.print("[green]Updated.[/green] Nothing changed.")
        return
    clean = outcome.changed - outcome.conflicts
    _output.console.print(
        "[green]Updated.[/green] Review the diff before committing — "
        f"conflicts are marked inline. {clean} clean, {outcome.conflicts} conflicted."
    )


def _run_engine_update(  # noqa: PLR0915 - one branch per prepare/apply/degraded/finalise stage, mirroring _run_engine's own linear-orchestration justification
    project: Path, *, dry_run: bool, degraded: bool
) -> None:
    """The engine-native `update` route (ADR 0041 rules 9-23, ADR 0046)."""
    from create_forge import engine, pipeline, update  # noqa: PLC0415

    # ADR 0053: recovery guidance is only ever printed once the clean-tree
    # precondition has passed. Before it, whatever is dirty is the user's own
    # work, and telling them to restore it away would destroy it.
    started = False
    try:
        update.require_clean_tree(project)
        started = True
        degraded_reason: str | None = None

        if degraded:
            recorded, new = pipeline.prepare_degraded_update(project)
            new_files = {file.target: file.content for file in new.files}
            update.preflight_update(
                project,
                metadata_filename=engine.generation_metadata_target(),
                targets=new_files,
                recorded_targets=recorded.digests,
            )
            outcome = update.degraded_plan(
                project,
                new_files,
                recorded_digests=recorded.digests,
                dry_run=dry_run,
            )
            degraded_reason = "requested with --degraded"
        else:
            try:
                preparation = pipeline.prepare_update(project)
            except pipeline.UnavailableRecordedReleaseError as exc:
                if not _confirm_degraded(str(exc)):
                    _output.err.print(f"[red]{exc}[/red]")
                    raise typer.Exit(3) from exc
                recorded, new = pipeline.prepare_degraded_update(project)
                new_files = {file.target: file.content for file in new.files}
                update.preflight_update(
                    project,
                    metadata_filename=engine.generation_metadata_target(),
                    targets=new_files,
                    recorded_targets=recorded.digests,
                )
                outcome = update.degraded_plan(
                    project,
                    new_files,
                    recorded_digests=recorded.digests,
                    dry_run=dry_run,
                )
                degraded_reason = str(exc)
            else:
                new = preparation.new
                # ADR 0052: refuse the whole update before its first mutation.
                # Plan targets already cover every recorded target the plan
                # acts on, so the recorded document itself is not re-read here.
                update.preflight_update(
                    project,
                    metadata_filename=engine.generation_metadata_target(),
                    targets=[item.target for item in preparation.plan.targets],
                    renames=preparation.plan.renames,
                )
                update.apply_renames(project, preparation.plan.renames, dry_run=dry_run)
                outcome = update.apply_plan(
                    project,
                    preparation.plan.targets,
                    preparation.plan.renames,
                    old=preparation.old,
                    new={file.target: file.content for file in preparation.new.files},
                    dry_run=dry_run,
                )

        if dry_run:
            _print_dry_run_summary(outcome)
            _output.console.print(
                "[green]Dry run complete.[/green] No project files changed."
            )
            return

        relock_warning = update.relock(project)
        if new.metadata is None:
            msg = "the engine returned no generation metadata for this render"
            raise StagingError(msg)
        refreshed = engine.metadata_json(new.metadata, degraded_reason=degraded_reason)
        update.write_recorded(
            project,
            metadata_filename=engine.generation_metadata_target(),
            content=refreshed,
        )
        update.stage_result(project)

        if relock_warning:
            _output.err.print(f"[yellow]{relock_warning}[/yellow]")
        _report_update_result(outcome)
    except KeyboardInterrupt:
        _output.err.print("\n[dim]Cancelled.[/dim]")
        _print_recovery(project, started=started)
        raise typer.Exit(130) from None
    except (update.UpdateError, StagingError) as exc:
        _output.err.print(f"[red]{exc}[/red]")
        _print_recovery(project, started=started)
        raise typer.Exit(1) from exc
    except engine.EngineCompatibilityError as exc:
        _output.err.print(f"[red]{exc}[/red]")
        raise typer.Exit(3) from exc
    except engine.ForgeEngineError as exc:
        _output.err.print(f"[red]{engine.explain(exc)}[/red]")
        _print_recovery(project, started=started)
        raise typer.Exit(1) from exc


def _print_recovery(project: Path, *, started: bool) -> None:
    """Rule 18 (ADR 0053): guidance for the repository's *actual* Git state.

    Read from Git at failure time, so a failure that changed nothing says so
    rather than printing a command, and a staged or half-renamed tree gets one
    that actually restores it. Printed, never run. `soft_wrap` and no markup or
    highlighting keep a command on one line, unmangled, ready to paste.
    """
    if not started:
        return
    from create_forge import update  # noqa: PLC0415

    for line in update.recovery_guidance(project).lines():
        _output.err.print(
            line, style="dim", markup=False, highlight=False, soft_wrap=True
        )
