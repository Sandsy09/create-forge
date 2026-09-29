"""`commands/new.py` -- the default engine route: `_run_engine` and the
render/finalise/failure paths it drives (CF-07.01 / #49, ADR 0014; the
default since the Engine-Default Cutover, ADR 0049).
"""

from __future__ import annotations

import builtins
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
from forge_template import (
    ComponentOwner,
    EngineInfo,
    GenerationPlan,
    PlannedFile,
    RenderedFile,
    RenderedProject,
)
from typer.testing import CliRunner

import create_forge.lifecycle as lifecycle_module
import create_forge.staging as staging_module
from create_forge import engine as engine_module
from create_forge import pipeline as pipeline_module
from create_forge.cli import app
from create_forge.pipeline import GenerationRequest
from create_forge.runner import ScaffoldRequest
from create_forge.staging import StagingError
from tests.commands import support
from tests.staging_probe import staging_siblings

if TYPE_CHECKING:
    from collections.abc import Mapping

runner = CliRunner()


def test_new_fails_closed_when_the_engine_cannot_be_imported(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """A broken environment where `forge-template` -- a required dependency
    since ADR 0040 (CF-18.01) -- somehow cannot be imported must fail closed
    at exit `3` (decision 12's widened provider-availability class), not
    crash the whole command with a raw traceback or fall back to scaffolding.

    Blocking via `sys.modules["forge_template"] = None` alone is not
    reliable here: `create_forge.engine`/`create_forge.pipeline` are already
    imported by other test modules in this same process, and CPython's
    `from package import submodule` machinery can satisfy that from the
    parent package's already-set `submodule` attribute without re-executing
    the submodule at all, even after deleting it from `sys.modules`.
    Patching `builtins.__import__` intercepts the actual import call
    `cli.py` makes, regardless of caching.
    """
    real_import = builtins.__import__

    def blocking_import(
        name: str,
        globals: Mapping[str, object] | None = None,  # noqa: A002 - matches __import__
        locals: Mapping[str, object] | None = None,  # noqa: A002 - matches __import__
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "create_forge" and "pipeline" in fromlist:
            msg = "forge_template not installed (simulated)"
            raise ImportError(msg)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocking_import)

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(tmp_path / "proj"),
            *support.ENGINE_ANSWERS,
        ],
    )

    assert result.exit_code == 3, result.output
    assert "forge-template is not installed" in result.output
    assert recorder == []
    assert not (tmp_path / "proj").exists()


def test_new_generates_a_real_cli_application(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[ScaffoldRequest],
    tmp_path: Path,
) -> None:
    """The real, unmocked engine: the installed `forge-template` production
    catalogue (since 0.3.0, CF-08.02) makes the default `new` path generate
    for real, superseding the Stage 06-era empty-catalogue rejection this
    test replaces -- see
    `tests/test_pipeline.py::test_build_generation_request_succeeds_against_the_real_catalogue`
    for the equivalent pipeline-level proof.
    """
    dest = tmp_path / "proj"

    def fake_lock(staging_dir: Path) -> None:
        (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setattr(staging_module, "create_uv_lock", fake_lock)

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *support.ENGINE_ANSWERS,
            "--archetype",
            "cli",
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder == []
    assert (dest / "src" / "engine_preview" / "cli.py").exists()
    assert (dest / "uv.lock").is_file()
    pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert 'engine-preview = "engine_preview.cli:app"' in pyproject


def test_new_exits_3_on_incompatible_engine(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
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

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(tmp_path / "proj"),
            *support.ENGINE_ANSWERS,
        ],
    )

    assert result.exit_code == 3, result.output
    assert recorder == []
    assert not (tmp_path / "proj").exists()


def test_new_rejects_a_non_empty_destination_before_the_engine(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """ADR 0015: the destination conflict is checked before the engine is
    even imported, let alone negotiated or validated against.
    """
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "existing.txt").write_text("hi", encoding="utf-8")

    def unexpected_get_engine_info() -> EngineInfo:
        raise AssertionError("the engine must not be reached for a conflict")

    monkeypatch.setattr(engine_module, "get_engine_info", unexpected_get_engine_info)

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *support.ENGINE_ANSWERS,
        ],
    )

    assert result.exit_code == 1, result.output
    # Rich wraps long lines to the console width, which varies by
    # environment (narrower in CI than a local wide terminal) -- normalise
    # whitespace before matching so a mid-phrase line break can't fail this.
    normalised_output = " ".join(result.output.split())
    assert "already exists and is not empty" in normalised_output
    assert recorder == []
    assert (dest / "existing.txt").read_text(encoding="utf-8") == "hi"


def test_new_dry_run_lists_targets_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """`--dry-run` short-circuits before staging (ADR 0015).
    `build_generation_request` is faked here with a successful result --
    the same technique test_pipeline.py uses -- so this exercises the
    dry-run branch in isolation from a real render.
    """
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda _root: pytest.fail("dry-run must not create a lockfile"),
    )

    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *support.ENGINE_ANSWERS,
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "pyproject.toml" in result.output
    assert recorder == []
    assert not dest.exists()


def test_new_finalises_a_successful_render(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """A successful (faked) render is staged and moved into place exactly
    like the Copier path, and reports success as `create-forge update`-able
    (ADR 0015, CF-18.04).
    """
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
        metadata=support.synthetic_metadata(),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )

    def fake_lock(staging_dir: Path) -> None:
        (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setattr(staging_module, "create_uv_lock", fake_lock)
    # This test is about CLI orchestration and staging, not the real Git/hook
    # lifecycle -- that is `tests/test_lifecycle.py`'s and the e2e suite's job
    # (CF-18.03). Faked here so this fast test needs no git identity.
    monkeypatch.setattr(lifecycle_module, "finalise_project", lambda dst: ())

    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *support.ENGINE_ANSWERS,
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder == []
    assert (dest / "pyproject.toml").read_bytes() == b"[project]\n"
    assert (dest / "uv.lock").is_file()
    assert (dest / ".forge" / "generation.json").is_file()
    assert "created at" in result.output
    # Normalise whitespace: Rich wraps long lines to the console width,
    # which varies by environment (see the destination-conflict test above).
    normalised_output = " ".join(result.output.split())
    assert "Pull later changes with: create-forge update" in normalised_output
    assert "uv run poe check" in normalised_output


def test_new_prints_a_lifecycle_warning_and_still_exits_0(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """A `git`/`pre-commit` lifecycle failure after a good render keeps the
    project and warns, rather than discarding a sound render (ADR 0041 rule
    4). `lifecycle.finalise_project` owns the real failure handling
    (`tests/test_lifecycle.py`); this only proves `cli.py` prints what it
    returns and does not turn a warning into a non-zero exit.
    """
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
        metadata=support.synthetic_metadata(),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda staging_dir: (staging_dir / "uv.lock").write_text(
            "version = 1\n", encoding="utf-8"
        ),
    )
    monkeypatch.setattr(
        lifecycle_module,
        "finalise_project",
        lambda dst: ("git commit failed; finish it yourself: git -C ... commit ...",),
    )

    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *support.ENGINE_ANSWERS,
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder == []
    assert "git commit failed" in result.output
    assert "created at" in result.output
    assert (dest / "pyproject.toml").is_file()


def test_new_reports_lock_failure_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[ScaffoldRequest],
    tmp_path: Path,
) -> None:
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
        metadata=support.synthetic_metadata(),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )

    def failing_lock(_root: Path) -> None:
        raise StagingError("uv lock failed")

    monkeypatch.setattr(staging_module, "create_uv_lock", failing_lock)
    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *support.ENGINE_ANSWERS,
        ],
    )

    assert result.exit_code == 1, result.output
    assert "uv lock failed" in result.output
    assert staging_siblings(dest) == []
    assert recorder == []
    assert not dest.exists()


def test_new_engine_keyboard_interrupt_leaves_nothing_behind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """CF-25.01: the engine route's equivalent of
    `test_new_legacy_keyboard_interrupt_leaves_nothing_behind`.
    `staging.staged`'s `except BaseException` covers this, not just
    `pipeline.finalise_files`'s own `StagingError` callers.
    """
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
        metadata=support.synthetic_metadata(),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )

    def interrupting_lock(_root: Path) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(staging_module, "create_uv_lock", interrupting_lock)
    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *support.ENGINE_ANSWERS,
        ],
    )

    assert result.exit_code == 130
    assert not dest.exists()
    assert staging_siblings(dest) == []
