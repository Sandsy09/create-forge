"""CLI behaviour via Typer's CliRunner.

`scaffold` is monkeypatched with a recorder so these assert the resolved
`ScaffoldRequest` rather than actually invoking Copier -- `ScaffoldRequest` is
frozen/slots, so it compares by value. The one real network scaffold lives in
docs/plan-v0.1.0.md's manual verification steps, not in this fast suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import create_forge.cli as cli_module
from create_forge.cli import app
from create_forge.config import UserConfig, config_path
from create_forge.runner import ScaffoldRequest

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point config_path() at a throwaway directory with no FORGE_* leakage.

    Without this, `new`/`doctor`/`config` would read the developer's real
    ~/.config/create-forge/config.toml and environment, making these tests
    depend on who runs them -- the same reasoning as test_config.py's
    _clean_forge_env, extended to also isolate the file path.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for field in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{field.upper()}", raising=False)
    return config_path()


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> list[ScaffoldRequest]:
    calls: list[ScaffoldRequest] = []

    def fake_scaffold(request: ScaffoldRequest) -> None:
        calls.append(request)

    # Patch the name inside cli, not runner -- cli.py imports scaffold
    # directly, so patching create_forge.runner.scaffold would not affect
    # the reference `new()` actually calls.
    monkeypatch.setattr(cli_module, "scaffold", fake_scaffold)
    return calls


def _write_config(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_list_shows_the_bundled_templates() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "library" in result.output


def test_doctor_reports_on_the_registry() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exception is None
    assert "registry" in result.output


def test_new_dry_run_records_the_request_and_writes_nothing(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "new",
            "My Project",
            "--yes",
            "--dry-run",
            "--path",
            str(dest),
            "--data",
            "project_description=x",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(recorder) == 1
    request = recorder[0]
    assert request.dry_run is True
    assert request.dst == dest.resolve()
    assert request.data["project_name"] == "My Project"
    assert not dest.exists()


def test_new_data_coerces_true_and_false_to_bool(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "Bool Project",
            "--yes",
            "--dry-run",
            "--path",
            str(tmp_path / "proj"),
            "--data",
            "use_docs=true",
            "--data",
            "some_flag=FALSE",
        ],
    )

    assert result.exit_code == 0, result.output
    request = recorder[0]
    assert request.data["use_docs"] is True
    assert request.data["some_flag"] is False


def test_new_yes_without_a_project_name_is_rejected(
    recorder: list[ScaffoldRequest],
) -> None:
    result = runner.invoke(app, ["new", "--yes"])
    assert result.exit_code == 1
    assert recorder == []


def test_new_bad_data_format_is_rejected(recorder: list[ScaffoldRequest]) -> None:
    result = runner.invoke(app, ["new", "X", "--yes", "--data", "no-equals-sign"])
    assert result.exit_code != 0
    assert recorder == []


def test_new_unknown_template_exits_with_an_explanation(
    recorder: list[ScaffoldRequest],
) -> None:
    result = runner.invoke(app, ["new", "X", "--yes", "--template", "does-not-exist"])
    assert result.exit_code == 1
    assert recorder == []
    assert "unknown template" in result.output


# --- config wiring (issue #3) ------------------------------------------------


def test_new_config_reaches_scaffold_data(
    recorder: list[ScaffoldRequest], _isolated_config: Path, tmp_path: Path
) -> None:
    _write_config(
        _isolated_config,
        'author_name = "Config Author"\ngithub_org = "config-org"\n',
    )

    result = runner.invoke(
        app,
        [
            "new",
            "Demo",
            "--yes",
            "--dry-run",
            "--path",
            str(tmp_path / "demo"),
            "--data",
            "project_description=x",
        ],
    )

    assert result.exit_code == 0, result.output
    data = recorder[0].data
    assert data["author_name"] == "Config Author"
    assert data["github_org"] == "config-org"


def test_new_data_overrides_config(
    recorder: list[ScaffoldRequest], _isolated_config: Path, tmp_path: Path
) -> None:
    _write_config(_isolated_config, 'github_org = "config-org"\n')

    result = runner.invoke(
        app,
        [
            "new",
            "Demo",
            "--yes",
            "--dry-run",
            "--path",
            str(tmp_path / "demo"),
            "--data",
            "project_description=x",
            "--data",
            "github_org=override-org",
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder[0].data["github_org"] == "override-org"


def test_new_malformed_config_is_a_user_error(
    _isolated_config: Path, recorder: list[ScaffoldRequest]
) -> None:
    _write_config(_isolated_config, "not = [valid toml")

    result = runner.invoke(app, ["new", "X", "--yes"])

    assert result.exit_code == 1
    assert recorder == []
    assert "not valid TOML" in result.output


def test_new_unknown_default_template_names_the_config_path(
    _isolated_config: Path, recorder: list[ScaffoldRequest]
) -> None:
    _write_config(_isolated_config, 'default_template = "does-not-exist"\n')

    result = runner.invoke(app, ["new", "X", "--yes"])

    # Rich wraps long lines in CliRunner's fixed-width capture, so compare
    # with newlines collapsed rather than requiring one contiguous substring.
    flattened = result.output.replace("\n", "")

    assert result.exit_code == 1
    assert recorder == []
    assert str(_isolated_config) in flattened
    assert "does-not-exist" in flattened


def test_config_init_writes_the_example_file(_isolated_config: Path) -> None:
    assert not _isolated_config.exists()

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0, result.output
    assert _isolated_config.exists()


def test_config_init_never_overwrites(_isolated_config: Path) -> None:
    _write_config(_isolated_config, "custom content")

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0, result.output
    assert _isolated_config.read_text(encoding="utf-8") == "custom content"


def test_config_show_reports_resolved_values(_isolated_config: Path) -> None:
    _write_config(_isolated_config, 'author_name = "Config Author"\n')

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
