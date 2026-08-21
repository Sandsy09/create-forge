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
from create_forge.runner import ScaffoldRequest

runner = CliRunner()


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
