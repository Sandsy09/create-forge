"""CLI behaviour that belongs to `cli.py` itself, not to any one command's
orchestration: `--help`/no-args exit codes, the full flag surface Typer
registers for `new`/`update`, and the `main()` group callback that hardens
console encoding before any subcommand runs.

CF-25.03 moved every command's own behaviour out of this file into
`tests/commands/*.py`, one module per `src/create_forge/commands/*.py`
module -- see `docs/cli-command-map.md`'s "Test map" section for the full
old-location -> new-location table. What stays here tests the thin Typer
layer, not any command's real logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from create_forge.cli import app
from create_forge.commands import _output as output_module
from create_forge.config import UserConfig, config_path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point config_path() at a throwaway directory with no FORGE_* leakage,
    same as `tests/commands/conftest.py`'s fixture of the same name -- kept
    local here rather than shared, so this root-level file has no import
    dependency on the `tests/commands/` package.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("COPIER_CACHE_DIR", str(tmp_path / "copier-cache"))
    for field in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{field.upper()}", raising=False)
    return config_path()


# --------------------------------------------------------------------------- #
# --help (CF-25.01: nothing previously invoked this through CliRunner)        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["new", "--help"],
        ["list", "--help"],
        ["update", "--help"],
        ["doctor", "--help"],
        ["config", "--help"],
        ["config", "init", "--help"],
        ["config", "show", "--help"],
    ],
    ids=" ".join,
)
def test_help_exits_zero(args: list[str]) -> None:
    """A cheap, strong regression signal for a file-move refactor (CF-25.02):
    Typer/Click builds `--help` from wherever a command's function is
    actually registered, so a command that stops registering correctly after
    moving to `commands/*` fails here, not just at runtime. Exit code only --
    not the rendered text (see `_command_params` below for why).
    """
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output


def _command_params(*names: str) -> dict[str, object]:
    """Every Click parameter registered on `create-forge <names...>`, by
    every one of its option strings.

    The same approach `test_engine_default_contract.py::_new_params` and
    `test_engine_lifecycle_contract.py::_update_params` already use --
    reading the live Click command object, not scraping rendered `--help`
    text. CF-25.01 first wrote a text-scraping version of this; it passed
    locally but failed on every CI runner (Linux and Windows alike) with an
    option's own flag string missing from `--help`'s *rendered* output
    despite exit code `0` and no exception -- a real, unexplained
    environment divergence in Typer's Rich-based renderer, not a terminal-
    width wrapping issue (a much wider forced `COLUMNS` did not fix it).
    Reading the command object instead sidesteps whatever that divergence
    is: it is the same data `--help` renders *from*, before any Rich
    formatting is involved.
    """
    command = typer.main.get_command(app)
    for name in names:
        command = command.commands[name]  # type: ignore[attr-defined]
    params: dict[str, object] = {}
    for param in command.params:
        for opt in param.opts:
            params[opt] = param
    return params


def test_new_registers_every_route_and_selection_flag() -> None:
    params = _command_params("new")
    for flag in (
        "--template",
        "--yes",
        "--legacy",
        "--archetype",
        "--capability",
        "--no-capabilities",
        "--platform",
        "--no-platforms",
        "--component-option",
        "--engine-source",
        "--engine-ref",
        "--dry-run",
    ):
        assert flag in params, f"{flag} is not a registered `new` option"


def test_update_registers_its_flags() -> None:
    params = _command_params("update")
    for flag in ("--ref", "--dry-run", "--legacy", "--degraded"):
        assert flag in params, f"{flag} is not a registered `update` option"


def test_no_args_is_help_and_exits_2() -> None:
    """Typer's `no_args_is_help=True` prints help but is still a usage
    non-answer, not a successful invocation -- matches `--help`'s own exit
    `0` being a *different* case from calling the app with nothing at all.
    """
    result = runner.invoke(app, [])
    assert result.exit_code == 2


def test_every_invocation_hardens_console_encoding_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`main()` is Typer's group callback, run before any subcommand -- the
    only hook that sees a harness's swapped `sys.stdout`/`sys.stderr` (such as
    `CliRunner`'s own, per invocation) rather than whatever was current when
    this module was first imported.
    """
    calls: list[None] = []
    monkeypatch.setattr(
        output_module, "_harden_console_encoding", lambda: calls.append(None)
    )

    runner.invoke(app, ["list"])

    assert calls
