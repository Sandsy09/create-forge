"""`commands/update.py` -- the Copier (`--legacy`-metadata-routed) `update`
path: `_run_copier_update` and the file-based routing that reaches it.
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

import create_forge.runner as runner_module
from create_forge import engine as engine_module
from create_forge.cli import app
from create_forge.runner import ScaffoldError

if TYPE_CHECKING:
    from collections.abc import Mapping

runner = CliRunner()


@pytest.fixture
def update_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Path, str | None, bool]]:
    calls: list[tuple[Path, str | None, bool]] = []

    def fake_update(
        project: Path, *, vcs_ref: str | None = None, dry_run: bool = False
    ) -> None:
        calls.append((project, vcs_ref, dry_run))

    # `update_project` imports `update` lazily from `create_forge.runner` on
    # every invocation (ADR 0040, CF-18.01), so patching it here is what
    # actually reaches the CLI's Copier `update` route.
    monkeypatch.setattr(runner_module, "update", fake_update)
    return calls


def _copier_project(tmp_path: Path) -> Path:
    """A project directory routed to the Copier update route (CF-18.04, ADR
    0041 rule 7): a `.copier-answers.yml` and no `.forge/generation.json`.
    """
    project = tmp_path / "project"
    project.mkdir()
    (project / ".copier-answers.yml").write_text("_src_path: x\n", encoding="utf-8")
    return project


def test_update_dry_run_forwards_ref_and_reports_no_changes(
    update_recorder: list[tuple[Path, str | None, bool]], tmp_path: Path
) -> None:
    project = _copier_project(tmp_path)

    result = runner.invoke(
        app, ["update", str(project), "--ref", "v1.1.0", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert update_recorder == [(project.resolve(), "v1.1.0", True)]
    assert "Dry run complete." in result.output
    assert "No project files changed." in result.output
    assert "Updated." not in result.output


def test_update_without_dry_run_preserves_current_behavior(
    update_recorder: list[tuple[Path, str | None, bool]], tmp_path: Path
) -> None:
    project = _copier_project(tmp_path)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 0, result.output
    assert update_recorder == [(project.resolve(), None, False)]
    assert "Updated." in result.output
    assert "Review the diff before committing" in result.output
    assert "Dry run complete." not in result.output


def test_update_failure_exits_1_without_a_success_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_update(
        _project: Path, *, vcs_ref: str | None = None, dry_run: bool = False
    ) -> None:
        del vcs_ref, dry_run
        raise ScaffoldError("update failed")

    monkeypatch.setattr(runner_module, "update", fail_update)
    project = _copier_project(tmp_path)

    result = runner.invoke(app, ["update", str(project), "--dry-run"])

    assert result.exit_code == 1
    assert "update failed" in result.output
    assert "Updated." not in result.output
    assert "Dry run complete." not in result.output


def test_update_legacy_revalidates_the_recorded_credential_bearing_src_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The Copier update route stays reachable, but a hostile recorded
    `_src_path` is still rejected before Copier's own `run_update` is ever
    called (ADR 0036) -- distinct from `tests/test_sources.py`'s direct
    `runner.update()` unit coverage, this proves the same guard survives the
    CLI's file-based routing (ADR 0041 rule 7). The real `runner.update` runs
    here (no `update_recorder` fixture, which would fake it away entirely and
    so never exercise the validation at all), with only Copier's own
    `run_update` faked to prove it is never reached.
    """

    def _unexpected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("run_update must not be reached")

    monkeypatch.setattr(runner_module, "run_update", _unexpected)
    project = _copier_project(tmp_path)
    (project / ".copier-answers.yml").write_text(
        "_src_path: https://user:secret@example.com/template.git\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 1, result.output
    assert "secret" not in result.output


def test_update_legacy_route_survives_an_unusable_engine(
    update_recorder: list[tuple[Path, str | None, bool]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A `.copier-answers.yml` project stays updatable even when the
    installed engine cannot be imported (ADR 0047 rule 3) -- the
    metadata-filename lookup that gates routing must not depend on it."""

    def _unusable() -> str:
        raise ImportError("forge_template has no DEFAULT_GENERATION_METADATA_TARGET")

    monkeypatch.setattr(engine_module, "generation_metadata_target", _unusable)
    project = _copier_project(tmp_path)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 0, result.output
    assert len(update_recorder) == 1
    assert update_recorder[0][0] == project.resolve()


def test_update_legacy_engine_unusable_and_no_copier_answers_exits_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With no `.copier-answers.yml` to fall back to, an unusable engine is
    a provider-availability failure (exit `3`), not a routing failure."""

    def _unusable() -> str:
        raise ImportError("forge_template has no DEFAULT_GENERATION_METADATA_TARGET")

    monkeypatch.setattr(engine_module, "generation_metadata_target", _unusable)
    project = tmp_path / "project"
    project.mkdir()

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 3, result.output


def test_update_legacy_without_the_extra_exits_3_naming_the_remedy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The file-routed Copier `update` path names the remedy even though the
    user passed no `--legacy` flag at all (ADR 0047 rule 4)."""
    real_import = builtins.__import__

    def blocking_import(
        name: str,
        globals: Mapping[str, object] | None = None,  # noqa: A002 - matches __import__
        locals: Mapping[str, object] | None = None,  # noqa: A002 - matches __import__
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "create_forge.runner":
            msg = "copier not installed (simulated)"
            raise ImportError(msg)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocking_import)
    project = _copier_project(tmp_path)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 3, result.output
    assert "pip install" in result.output
    assert "create-forge[legacy]" in result.output
    assert ".copier-answers.yml" in result.output
