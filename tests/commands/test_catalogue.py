"""`commands/catalogue.py` -- `list`."""

from __future__ import annotations

import pytest
from forge_template import EngineInfo
from typer.testing import CliRunner

from create_forge import engine as engine_module
from create_forge.cli import app
from create_forge.commands import catalogue as catalogue_module

runner = CliRunner()


def test_list_shows_the_bundled_templates() -> None:
    result = runner.invoke(app, ["list", "--legacy"])
    assert result.exit_code == 0
    assert "library" in result.output


def test_list_legacy_broken_registry_is_a_user_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF-25.01: a real bug found while characterising `list`. Every other
    command that reads the bundled registry (`doctor`, `new`'s
    `_select_template`) catches `RuntimeError` and prints a clean message;
    `_list_legacy_registry` did not, so a broken registry crashed with a raw
    traceback instead of a plain exit `1` -- the one inconsistency in an
    otherwise uniform "no traceback reaches the user" convention (CLAUDE.md).
    """

    def _broken_registry() -> object:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(catalogue_module, "load_registry", _broken_registry)

    result = runner.invoke(app, ["list", "--legacy"])

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "boom" in result.output


def test_list_shows_the_discovered_engine_catalogue_by_default() -> None:
    """ADR 0040 decisions 7/9 (CF-18.01): `list` with no flag shows the
    engine's own discovered catalogue, not the bundled registry.
    """
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert "library" in result.output
    assert "archetype" in result.output


def test_list_exits_3_on_incompatible_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default engine route's compatibility check applies to `list` the
    same way it applies to `new` -- untested until CF-25.01.
    """
    monkeypatch.setattr(
        engine_module,
        "get_engine_info",
        lambda: EngineInfo(
            package_version="9.0.0",
            projectspec_protocols=(99,),
            component_manifest_protocols=(1,),
            metadata_version=1,
        ),
    )

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 3, result.output
