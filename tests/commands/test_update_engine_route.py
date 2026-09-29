"""`commands/update.py` -- the engine-native `update` route (CF-18.04, ADR
0041 rules 9-23, ADR 0046) and its target containment (CF-22.01, ADR 0052).

`create_forge.update`'s own apply/merge/degraded logic is unit-tested in
`tests/test_update_engine.py`; this proves the CLI orchestrates it
correctly -- classification counts, dry-run output, recovery guidance, exit
codes -- against a real Git repository with only `pipeline.prepare_update`/
`prepare_degraded_update` and `update`'s own apply/relock/stage functions
faked.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
import typer
from forge_template import GenerationMetadata
from typer.testing import CliRunner

from create_forge import pipeline as pipeline_module
from create_forge.cli import app
from create_forge.update import RecordedDocument, TargetResult
from create_forge.update import UpdateOutcome as _UpdateOutcome
from tests.commands import support

runner = CliRunner()


@dataclass(frozen=True, slots=True)
class _FakeFile:
    target: str
    content: bytes


@dataclass(frozen=True, slots=True)
class _FakeRendered:
    files: tuple[_FakeFile, ...]
    metadata: GenerationMetadata


@dataclass(frozen=True, slots=True)
class _FakePlan:
    targets: tuple[object, ...]
    renames: tuple[object, ...] = ()


def _metadata_path(project: Path) -> Path:
    return project / ".forge" / "generation.json"


def _engine_project(tmp_path: Path) -> Path:
    """A real, clean Git repo with a `.forge/generation.json` -- the engine
    route's own precondition (`update.require_clean_tree`).
    """
    project = tmp_path / "project"
    project.mkdir()
    (project / ".forge").mkdir()
    _metadata_path(project).write_text(
        support.synthetic_metadata().to_json(), encoding="utf-8"
    )

    def _git(*args: str) -> None:
        subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            cwd=project,
            check=True,
            capture_output=True,
        )

    _git("init", "--quiet", "--initial-branch=main")
    _git("config", "user.name", "Test")
    _git("config", "user.email", "test@example.com")
    _git("add", "-A")
    _git("commit", "--quiet", "-m", "initial")
    return project


def test_engine_update_reports_nothing_changed_on_a_no_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)
    metadata = support.synthetic_metadata()
    fake_new = _FakeRendered(files=(_FakeFile("f.txt", b"x"),), metadata=metadata)
    fake_preparation = pipeline_module.UpdatePreparation(
        plan=cast(Any, _FakePlan(targets=())),
        new=cast(Any, fake_new),
        old={"f.txt": b"x"},
        recorded=cast(Any, None),
    )
    monkeypatch.setattr(
        pipeline_module, "prepare_update", lambda project: fake_preparation
    )
    monkeypatch.setattr(
        "create_forge.update.apply_renames",
        lambda project, renames, dry_run=False: None,
    )
    monkeypatch.setattr(
        "create_forge.update.apply_plan",
        lambda *a, **k: _UpdateOutcome(results=()),
    )
    monkeypatch.setattr("create_forge.update.relock", lambda project: None)
    monkeypatch.setattr("create_forge.update.stage_result", lambda project: None)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 0, result.output
    assert "Nothing changed." in result.output
    metadata_path = _metadata_path(project)
    assert metadata_path.read_text(encoding="utf-8") == metadata.to_json()


def test_engine_update_reports_clean_and_conflicted_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)
    fake_new = _FakeRendered(files=(), metadata=support.synthetic_metadata())
    fake_preparation = pipeline_module.UpdatePreparation(
        plan=cast(Any, _FakePlan(targets=())),
        new=cast(Any, fake_new),
        old={},
        recorded=cast(Any, None),
    )
    monkeypatch.setattr(
        pipeline_module, "prepare_update", lambda project: fake_preparation
    )
    monkeypatch.setattr(
        "create_forge.update.apply_renames",
        lambda project, renames, dry_run=False: None,
    )
    monkeypatch.setattr(
        "create_forge.update.apply_plan",
        lambda *a, **k: _UpdateOutcome(
            results=(
                TargetResult("a.txt", "changed", "clean"),
                TargetResult("b.txt", "changed", "conflict"),
            )
        ),
    )
    monkeypatch.setattr("create_forge.update.relock", lambda project: None)
    monkeypatch.setattr("create_forge.update.stage_result", lambda project: None)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 0, result.output
    # Normalise whitespace: Rich wraps long lines to the console width.
    assert "1 clean, 1 conflicted" in " ".join(result.output.split())


def test_engine_update_dry_run_prints_the_classification_list_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)
    before = _metadata_path(project).read_text(encoding="utf-8")
    fake_new = _FakeRendered(files=(), metadata=support.synthetic_metadata())
    fake_preparation = pipeline_module.UpdatePreparation(
        plan=cast(Any, _FakePlan(targets=())),
        new=cast(Any, fake_new),
        old={},
        recorded=cast(Any, None),
    )
    monkeypatch.setattr(
        pipeline_module, "prepare_update", lambda project: fake_preparation
    )
    monkeypatch.setattr(
        "create_forge.update.apply_renames",
        lambda project, renames, dry_run=False: None,
    )
    monkeypatch.setattr(
        "create_forge.update.apply_plan",
        lambda *a, **k: _UpdateOutcome(
            results=(TargetResult("a.txt", "added", "clean"),)
        ),
    )

    result = runner.invoke(app, ["update", str(project), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "added" in result.output
    assert "a.txt" in result.output
    assert "Dry run complete." in result.output
    assert _metadata_path(project).read_text(encoding="utf-8") == before


@dataclass(frozen=True, slots=True)
class _FakeUpdateTarget:
    target: str
    classification: str
    regeneration: str = "replace"


@dataclass(frozen=True, slots=True)
class _FakeAppliedRename:
    component_id: str
    from_: str
    to: str
    since: str = "1.1.0"


def _git_text(*args: str, cwd: Path) -> str:
    return subprocess.run(  # noqa: S603 - fixed executable, reviewed args
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def _git_run(*args: str, cwd: Path) -> None:
    subprocess.run(  # noqa: S603 - fixed executable, reviewed args
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def test_engine_update_dry_run_with_a_rename_leaves_the_tree_and_index_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """create-forge#209's own reproduction: a dry run whose plan contains an
    owner-declared rename alongside a changed, a removed and an added target
    must not run `git mv` -- `apply_renames` and `apply_plan` run for real
    here, only `prepare_update` is stubbed.
    """
    project = _engine_project(tmp_path)
    (project / "moved-from.txt").write_bytes(b"moved content\n")
    (project / "changed.txt").write_bytes(b"old changed\n")
    (project / "removed.txt").write_bytes(b"old removed\n")
    _git_run("add", "-A", cwd=project)
    _git_run("commit", "--quiet", "-m", "seed", cwd=project)

    before_status = _git_text("status", "--porcelain", cwd=project)
    before_head = _git_text("rev-parse", "HEAD", cwd=project).strip()
    before_metadata = _metadata_path(project).read_bytes()

    fake_new = _FakeRendered(
        files=(
            _FakeFile("moved-to.txt", b"moved content (template)\n"),
            _FakeFile("changed.txt", b"new changed\n"),
            _FakeFile("added.txt", b"new added\n"),
        ),
        metadata=support.synthetic_metadata(),
    )
    fake_preparation = pipeline_module.UpdatePreparation(
        plan=cast(
            Any,
            _FakePlan(
                targets=(
                    _FakeUpdateTarget(target="moved-to.txt", classification="renamed"),
                    _FakeUpdateTarget(target="changed.txt", classification="changed"),
                    _FakeUpdateTarget(target="removed.txt", classification="removed"),
                    _FakeUpdateTarget(target="added.txt", classification="added"),
                ),
                renames=(
                    _FakeAppliedRename(
                        component_id="widget", from_="moved-from.txt", to="moved-to.txt"
                    ),
                ),
            ),
        ),
        new=cast(Any, fake_new),
        old={
            "moved-from.txt": b"moved content\n",
            "changed.txt": b"old changed\n",
            "removed.txt": b"old removed\n",
        },
        recorded=cast(Any, None),
    )
    monkeypatch.setattr(
        pipeline_module, "prepare_update", lambda project: fake_preparation
    )

    result = runner.invoke(app, ["update", str(project), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Dry run complete." in result.output
    assert _git_text("status", "--porcelain", cwd=project) == before_status == ""
    assert _git_text("rev-parse", "HEAD", cwd=project).strip() == before_head
    assert _metadata_path(project).read_bytes() == before_metadata
    assert (project / "moved-from.txt").read_bytes() == b"moved content\n"
    assert not (project / "moved-to.txt").exists()
    assert (project / "changed.txt").read_bytes() == b"old changed\n"
    assert (project / "removed.txt").read_bytes() == b"old removed\n"
    assert not (project / "added.txt").exists()


def test_engine_update_relock_warning_is_printed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)
    fake_new = _FakeRendered(files=(), metadata=support.synthetic_metadata())
    fake_preparation = pipeline_module.UpdatePreparation(
        plan=cast(Any, _FakePlan(targets=())),
        new=cast(Any, fake_new),
        old={},
        recorded=cast(Any, None),
    )
    monkeypatch.setattr(
        pipeline_module, "prepare_update", lambda project: fake_preparation
    )
    monkeypatch.setattr(
        "create_forge.update.apply_renames",
        lambda project, renames, dry_run=False: None,
    )
    monkeypatch.setattr(
        "create_forge.update.apply_plan", lambda *a, **k: _UpdateOutcome(results=())
    )
    monkeypatch.setattr(
        "create_forge.update.relock", lambda project: "uv lock failed somehow"
    )
    monkeypatch.setattr("create_forge.update.stage_result", lambda project: None)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 0, result.output
    assert "uv lock failed somehow" in result.output


def test_engine_update_dirty_tree_exits_1_and_prints_no_recovery_command(
    tmp_path: Path,
) -> None:
    """CF-22.02 (ADR 0053): the update never started, and the dirty files are
    the user's own work -- so no command that discards a working tree is
    printed. (Published 0.4.0 printed `git restore . && git clean -fd` here.)
    """
    project = _engine_project(tmp_path)
    (project / "untracked.txt").write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 1, result.output
    assert "uncommitted changes" in result.output
    assert "git restore" not in result.output
    assert "git clean" not in result.output
    assert (project / "untracked.txt").read_text(encoding="utf-8") == "x"


def test_engine_update_keyboard_interrupt_exits_130_and_reports_the_real_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)

    def _interrupt(project: Path) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(pipeline_module, "prepare_update", _interrupt)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 130, result.output
    assert "Cancelled." in result.output
    # Interrupted before anything was written: nothing to recover, and no command.
    assert "nothing to recover" in " ".join(result.output.split())
    assert "git restore" not in result.output


def test_engine_update_unavailable_release_declined_exits_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)

    def _unavailable(project: Path) -> object:
        raise pipeline_module.UnavailableRecordedReleaseError("0.4.9", "not found")

    monkeypatch.setattr(pipeline_module, "prepare_update", _unavailable)
    monkeypatch.setattr(typer, "confirm", lambda *a, **k: False)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 3, result.output
    assert "0.4.9" in result.output


def test_engine_update_unavailable_release_closed_stdin_declines_for_real(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CF-25.01: `_confirm_degraded`'s own docstring promises "closed stdin
    behaves as a decline", but every other test of this path patches
    `typer.confirm` directly, trusting the mock rather than proving the
    claim. `input=""` gives `CliRunner` a real, immediately-closed stdin --
    `typer.confirm` hits EOF for real and `_confirm_degraded`'s `except
    typer.Abort` is what actually runs.
    """
    project = _engine_project(tmp_path)

    def _unavailable(project: Path) -> object:
        raise pipeline_module.UnavailableRecordedReleaseError("0.4.9", "not found")

    monkeypatch.setattr(pipeline_module, "prepare_update", _unavailable)

    result = runner.invoke(app, ["update", str(project)], input="")

    assert result.exit_code == 3, result.output
    assert "0.4.9" in result.output


def test_engine_update_unavailable_release_accepted_runs_degraded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)
    fake_new = _FakeRendered(files=(), metadata=support.synthetic_metadata())
    recorded = RecordedDocument(raw="{}", provider_version="0.4.9", spec={}, digests={})

    def _unavailable(project: Path) -> object:
        raise pipeline_module.UnavailableRecordedReleaseError("0.4.9", "not found")

    monkeypatch.setattr(pipeline_module, "prepare_update", _unavailable)
    monkeypatch.setattr(
        pipeline_module,
        "prepare_degraded_update",
        lambda project: (recorded, cast(Any, fake_new)),
    )
    monkeypatch.setattr(typer, "confirm", lambda *a, **k: True)
    monkeypatch.setattr(
        "create_forge.update.degraded_plan",
        lambda *a, **k: _UpdateOutcome(
            results=(TargetResult("a.txt", "added", "clean"),)
        ),
    )
    monkeypatch.setattr("create_forge.update.relock", lambda project: None)
    monkeypatch.setattr("create_forge.update.stage_result", lambda project: None)

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 0, result.output
    assert "1 clean, 0 conflicted" in " ".join(result.output.split())
    written = json.loads(_metadata_path(project).read_text(encoding="utf-8"))
    assert written["reproduction"]["mode"] == "degraded"
    assert "0.4.9" in written["reproduction"]["reason"]
    assert "not found" in written["reproduction"]["reason"]


def test_engine_update_explicit_degraded_flag_records_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)
    fake_new = _FakeRendered(files=(), metadata=support.synthetic_metadata())
    recorded = RecordedDocument(raw="{}", provider_version="0.5.0", spec={}, digests={})

    monkeypatch.setattr(
        pipeline_module,
        "prepare_degraded_update",
        lambda project: (recorded, cast(Any, fake_new)),
    )
    monkeypatch.setattr(
        "create_forge.update.degraded_plan", lambda *a, **k: _UpdateOutcome(results=())
    )
    monkeypatch.setattr("create_forge.update.relock", lambda project: None)
    monkeypatch.setattr("create_forge.update.stage_result", lambda project: None)

    result = runner.invoke(app, ["update", str(project), "--degraded"])

    assert result.exit_code == 0, result.output
    written = json.loads(_metadata_path(project).read_text(encoding="utf-8"))
    assert written["reproduction"]["mode"] == "degraded"


def test_engine_update_refuses_an_unsafe_plan_target_before_any_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _engine_project(tmp_path)
    before = _metadata_path(project).read_text(encoding="utf-8")
    fake_new = _FakeRendered(files=(), metadata=support.synthetic_metadata())
    plan = _FakePlan(targets=(_FakeUpdateTarget("../outside/x.txt", "changed"),))
    monkeypatch.setattr(
        pipeline_module,
        "prepare_update",
        lambda project: pipeline_module.UpdatePreparation(
            plan=cast(Any, plan),
            new=cast(Any, fake_new),
            old={},
            recorded=cast(Any, None),
        ),
    )
    mutated: list[str] = []
    monkeypatch.setattr(
        "create_forge.update.apply_renames",
        lambda project, renames, dry_run=False: mutated.append("apply_renames"),
    )
    monkeypatch.setattr(
        "create_forge.update.apply_plan",
        lambda *a, **k: mutated.append("apply_plan"),
    )

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 1, result.output
    assert "unsafe update target" in " ".join(result.output.split())
    assert mutated == []
    assert _metadata_path(project).read_text(encoding="utf-8") == before


@pytest.mark.parametrize("dry_run", [False, True])
def test_engine_update_degraded_refuses_a_tampered_recorded_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dry_run: bool
) -> None:
    """The recorded digest matches the outside file -- the case that, before
    ADR 0052, was read (even in `--dry-run`) and then deleted.
    """
    project = _engine_project(tmp_path)
    outside = tmp_path / "sentinel.txt"
    outside.write_bytes(b"outside\n")
    digest = "sha256:" + hashlib.sha256(b"outside\n").hexdigest()
    fake_new = _FakeRendered(files=(), metadata=support.synthetic_metadata())
    recorded = RecordedDocument(
        raw="{}",
        provider_version="0.6.0",
        spec={},
        digests={"../sentinel.txt": digest},
    )
    monkeypatch.setattr(
        pipeline_module,
        "prepare_degraded_update",
        lambda project: (recorded, cast(Any, fake_new)),
    )
    args = ["update", str(project), "--degraded"]
    result = runner.invoke(app, [*args, "--dry-run"] if dry_run else args)

    assert result.exit_code == 1, result.output
    assert "unsafe update target" in " ".join(result.output.split())
    assert outside.read_bytes() == b"outside\n"
