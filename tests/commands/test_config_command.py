"""`commands/config.py` -- `config init` and `config show`.

Named `test_config_command.py`, not `test_config.py`, to stay distinct from
`tests/test_config.py`, which unit-tests `create_forge.config` (the module
this command reads/writes) directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from create_forge.cli import app
from tests.commands.support import write_config

runner = CliRunner()


def test_config_init_writes_the_example_file(_isolated_config: Path) -> None:
    assert not _isolated_config.exists()

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0, result.output
    assert _isolated_config.exists()


def test_config_init_never_overwrites(_isolated_config: Path) -> None:
    write_config(_isolated_config, "custom content")

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0, result.output
    assert _isolated_config.read_text(encoding="utf-8") == "custom content"


def test_config_show_reports_resolved_values(_isolated_config: Path) -> None:
    write_config(_isolated_config, 'author_name = "Config Author"\n')

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert "Config Author" in result.output
    assert "config file" in result.output


def test_config_show_reports_environment_source(
    _isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_GITHUB_ORG", "env-org")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert "env-org" in result.output
    assert "environment" in result.output


def test_config_show_malformed_config_is_a_user_error(_isolated_config: Path) -> None:
    """CF-25.01: `new`'s equivalent
    (`test_new_malformed_config_is_a_user_error`) was tested; `config show`'s
    own `_load_config_or_exit`-shaped handling was not.
    """
    write_config(_isolated_config, "not = [valid toml")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 1
    assert "not valid TOML" in result.output
