"""CF-22.02 (#194, ADR 0053): recovery guidance matches the repository's real state.

Real `git`, no network, no engine render -- the same fast-suite shape as
`tests/test_update_engine.py` and `tests/test_update_containment.py`, so this
runs in the CI `test` matrix and the `windows` job.

The previous hint (`git restore . && git clean -fd`) assumed a failed update
never leaves anything staged. It does: `apply_renames` runs `git mv`, which
stages the rename at once, and a completed update ends in `git add -A`. `git
restore .` restores the working tree from the *index*, so in either state it is
a no-op. Every test here builds a repository, drives the update's real
functions to a real state, and then **executes the commands `create-forge`
prints**, from outside the repository, asserting the recorded baseline is back:
index, working tree, additions, removals and renames, with a user-owned ignored
file untouched.

The installed-console half of this evidence is CF-22.03's.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from create_forge import engine as engine_module
from create_forge import pipeline as pipeline_module
from create_forge import update as update_module
from create_forge.cli import app
from create_forge.update import (
    CLEAN_COMMAND,
    CLEAN_PREVIEW_COMMAND,
    RESTORE_COMMAND,
    RecoveryGuidance,
    RecoveryState,
    UpdateError,
    apply_plan,
    apply_renames,
    recovery_guidance,
    stage_result,
    write_recorded,
)
from tests import recovery_recipes

runner = CliRunner()

METADATA = ".forge/generation.json"
USER_DATA = b"SECRET=do-not-touch\n"

STATES = [
    "unstaged_only",
    "after_git_mv",
    "before_staging",
    "partly_staged",
    "completed",
]
# The states in which the update's new file is still untracked.
UNTRACKED_STATES = {"unstaged_only", "before_staging", "partly_staged"}


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    ).stdout


def _run(argv: tuple[str, ...], cwd: Path) -> str:
    completed = subprocess.run(  # noqa: S603
        argv, cwd=cwd, check=True, capture_output=True, timeout=30
    )
    return completed.stdout.decode("utf-8", errors="replace")


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "--quiet", "--initial-branch=main", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "core.autocrlf", "false", cwd=path)


def _commit(path: Path) -> None:
    _git("add", "-A", cwd=path)
    _git("commit", "--quiet", "-m", "commit", cwd=path)


def _snapshot(root: Path) -> dict[str, bytes]:
    """Every file under `root` (ignored ones included) except `.git` itself."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


@dataclass(frozen=True, slots=True)
class _Target:
    target: str
    classification: str
    regeneration: str = "replace"


@dataclass(frozen=True, slots=True)
class _Rename:
    component_id: str
    from_: str
    to: str
    since: str = "1.1.0"


@dataclass(frozen=True, slots=True)
class _Repo:
    root: Path
    project: Path
    baseline: dict[str, bytes]


_TARGETS = [
    _Target("mod.txt", "changed"),
    _Target("gone.txt", "removed"),
    _Target("moved-to.txt", "renamed"),
    _Target("new.txt", "added"),
]
_RENAMES = [_Rename("c", "moved-from.txt", "moved-to.txt")]
_OLD = {
    "mod.txt": b"original mod\n",
    "gone.txt": b"original gone\n",
    "moved-from.txt": b"original moved\n",
}
_NEW = {
    "mod.txt": b"updated mod\n",
    "moved-to.txt": b"updated moved\n",
    "new.txt": b"brand new\n",
}


def _make_repo(tmp_path: Path, *, subdir: str | None = None) -> _Repo:
    """A committed project: a target the update will modify, remove, rename and
    add to, plus a tracked metadata file and a user-owned, gitignored file.
    """
    root = tmp_path / "repo"
    _init_repo(root)
    project = root / subdir if subdir else root
    (root / ".gitignore").write_text("local.env\n", encoding="utf-8")
    (project / ".forge").mkdir(parents=True)
    for name, content in _OLD.items():
        (project / name).write_bytes(content)
    (project / METADATA).write_bytes(b"{}\n")
    (project / "local.env").write_bytes(USER_DATA)
    _commit(root)
    return _Repo(root=root, project=project, baseline=_snapshot(root))


def _leave_state(repo: _Repo, state: str) -> None:
    """Drive the update's real functions as far as `state` says, then stop."""
    project = repo.project
    if state == "unstaged_only":
        apply_plan(
            project,
            [t for t in _TARGETS if t.classification != "renamed"],
            [],
            old=_OLD,
            new=_NEW,
            dry_run=False,
        )
        return
    apply_renames(project, _RENAMES)  # `git mv` stages the rename immediately
    if state == "after_git_mv":
        return
    apply_plan(project, _TARGETS, _RENAMES, old=_OLD, new=_NEW, dry_run=False)
    write_recorded(project, metadata_filename=METADATA, content='{"new": true}\n')
    if state == "before_staging":
        return
    if state == "partly_staged":
        _git("add", "mod.txt", cwd=project)  # `git add -A` interrupted part-way
        return
    stage_result(project)


def _assert_recovered(repo: _Repo) -> None:
    assert _git("status", "--porcelain", cwd=repo.root).strip() == ""
    assert _snapshot(repo.root) == repo.baseline
    assert (repo.project / "local.env").read_bytes() == USER_DATA


def _execute(guidance: RecoveryGuidance, *, cwd: Path) -> None:
    """Run the printed commands in order, reviewing untracked files first.

    `cwd` is deliberately outside the repository: the commands are anchored at
    the repository root and must not depend on where they are pasted.
    """
    restore, *review = guidance.commands()
    _run(restore, cwd)
    if review:
        preview, delete = review
        listing = _run(preview, cwd)
        assert "new.txt" in listing
        assert "local.env" not in listing  # ignored files are never candidates
        _run(delete, cwd)


# --------------------------------------------------------------------------- #
# The printed commands recover every state an update can leave behind          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("subdir", [None, "app"], ids=["repo-root", "subdirectory"])
@pytest.mark.parametrize("state", STATES)
def test_the_printed_commands_recover_the_recorded_baseline(
    tmp_path: Path, state: str, subdir: str | None
) -> None:
    repo = _make_repo(tmp_path, subdir=subdir)
    _leave_state(repo, state)
    assert _git("status", "--porcelain", cwd=repo.root).strip() != ""

    guidance = recovery_guidance(repo.project)

    assert guidance.state is RecoveryState.RESTORABLE
    assert guidance.has_untracked is (state in UNTRACKED_STATES)
    _execute(guidance, cwd=tmp_path)
    _assert_recovered(repo)


@pytest.mark.parametrize(
    ("state", "recovered"),
    [
        ("unstaged_only", True),
        ("after_git_mv", False),
        ("before_staging", False),
        ("partly_staged", False),
        ("completed", False),
    ],
)
def test_the_previous_hint_only_ever_recovered_a_purely_unstaged_update(
    tmp_path: Path, state: str, recovered: bool
) -> None:
    """The defect, reproduced: `git restore .` restores from the index, so it is
    a no-op once the update -- or an interrupted `git mv` -- has staged anything.
    """
    repo = _make_repo(tmp_path)
    _leave_state(repo, state)

    _git("restore", ".", cwd=repo.project)
    _git("clean", "-fd", cwd=repo.project)

    dirty = _git("status", "--porcelain", cwd=repo.root).strip() != ""
    assert dirty is not recovered
    assert (_snapshot(repo.root) == repo.baseline) is recovered


def test_the_untracked_preview_lists_new_files_and_never_ignored_ones(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _leave_state(repo, "before_staging")
    guidance = recovery_guidance(repo.project)
    restore, preview, delete = guidance.commands()

    _run(restore, tmp_path)
    listing = _run(preview, tmp_path)

    assert "new.txt" in listing
    assert "local.env" not in listing
    assert (repo.project / "new.txt").exists()  # the preview deleted nothing
    _run(delete, tmp_path)
    assert not (repo.project / "new.txt").exists()


def test_a_completed_update_has_nothing_untracked_to_review(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _leave_state(repo, "completed")

    guidance = recovery_guidance(repo.project)

    assert guidance.has_untracked is False
    assert len(guidance.commands()) == 1
    assert not any("clean" in " ".join(c) for c in guidance.commands())


# --------------------------------------------------------------------------- #
# The other states                                                             #
# --------------------------------------------------------------------------- #


def test_a_failure_that_changed_nothing_says_so(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    guidance = recovery_guidance(repo.project)

    assert guidance.state is RecoveryState.UNCHANGED
    assert guidance.commands() == ()
    assert guidance.lines() == ("No project files were changed; nothing to recover.",)


def test_ignored_files_alone_are_not_a_change(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    (repo.project / "local.env").write_bytes(b"EDITED=1\n")

    assert recovery_guidance(repo.project).state is RecoveryState.UNCHANGED


def test_a_repository_with_no_commit_gets_manual_guidance_and_no_command(
    tmp_path: Path,
) -> None:
    root = tmp_path / "empty"
    _init_repo(root)
    (root / "file.txt").write_text("x", encoding="utf-8")

    guidance = recovery_guidance(root)

    assert guidance.state is RecoveryState.NO_HEAD
    assert guidance.commands() == ()
    text = " ".join(guidance.lines())
    assert "no commit to restore from" in text
    assert "nothing was run for you" in text
    assert "git restore" not in text


def test_a_directory_that_is_not_a_repository_falls_back_to_the_superset(
    tmp_path: Path,
) -> None:
    guidance = recovery_guidance(tmp_path)

    assert guidance.state is RecoveryState.UNKNOWN
    assert guidance.root is None
    assert guidance.commands() == (
        ("git", *RESTORE_COMMAND[1:]),
        ("git", *CLEAN_PREVIEW_COMMAND[1:]),
        ("git", *CLEAN_COMMAND[1:]),
    )
    assert "repository root" in guidance.lines()[0]


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("git"),
        OSError("cannot launch"),
        subprocess.TimeoutExpired("git", 30),
    ],
    ids=["missing", "launch", "timeout"],
)
def test_guidance_never_raises_when_git_cannot_be_consulted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def _fail(*args: object, **kwargs: object) -> object:
        raise failure

    monkeypatch.setattr("create_forge.update.subprocess.run", _fail)

    guidance = recovery_guidance(tmp_path)

    assert guidance.state is RecoveryState.UNKNOWN
    assert guidance.commands()  # still the safe superset


def test_a_failing_status_falls_back_rather_than_guessing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    real = update_module._read_git

    def _read(args: list[str], cwd: Path) -> tuple[int, str] | None:
        if args and args[0] == "status":
            return 128, ""
        return real(args, cwd)

    monkeypatch.setattr(update_module, "_read_git", _read)

    guidance = recovery_guidance(repo.project)

    assert guidance.state is RecoveryState.UNKNOWN
    assert guidance.root is not None


# --------------------------------------------------------------------------- #
# What is printed                                                              #
# --------------------------------------------------------------------------- #


def test_the_printed_text_names_the_root_the_scope_and_the_review_step(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    _leave_state(repo, "before_staging")

    lines = recovery_guidance(repo.project).lines()

    text = " ".join(lines)
    assert str(repo.root) in lines[1]  # anchored at the repository root
    assert "whole repository" in text
    assert "discards any uncommitted work" in text
    assert "Review the untracked files" in text
    assert "&&" not in text  # one command per line; never a chained delete
    assert lines[1].lstrip().split()[:2] == ["git", "-C"]
    review = [line for line in lines if "clean" in line]
    assert review[0].endswith("-nd")  # the preview always precedes the delete
    assert review[1].endswith("-fd")


def test_the_cli_constants_are_the_documented_commands() -> None:
    assert " ".join(RESTORE_COMMAND) == recovery_recipes.RESTORE_COMMAND
    assert " ".join(CLEAN_PREVIEW_COMMAND) == recovery_recipes.CLEAN_PREVIEW_COMMAND
    assert " ".join(CLEAN_COMMAND) == recovery_recipes.CLEAN_COMMAND
    assert RESTORE_COMMAND == recovery_recipes.RESTORE_ARGV


# --------------------------------------------------------------------------- #
# Through the CLI: real apply_* steps, injected failures                       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _FakeFile:
    target: str
    content: bytes


@dataclass(frozen=True, slots=True)
class _FakeRendered:
    files: tuple[_FakeFile, ...]
    metadata: object


@dataclass(frozen=True, slots=True)
class _FakePlan:
    targets: tuple[_Target, ...]
    renames: tuple[_Rename, ...]


def _prepare(monkeypatch: pytest.MonkeyPatch) -> None:
    """Have `update` classify the fixture's plan; every apply step stays real."""
    rendered = _FakeRendered(
        files=tuple(_FakeFile(t, c) for t, c in _NEW.items()), metadata=object()
    )
    preparation = pipeline_module.UpdatePreparation(
        plan=cast(Any, _FakePlan(tuple(_TARGETS), tuple(_RENAMES))),
        new=cast(Any, rendered),
        old=_OLD,
        recorded=cast(Any, None),
    )
    monkeypatch.setattr(pipeline_module, "prepare_update", lambda project: preparation)


def _normalised(text: str) -> str:
    return " ".join(text.split())


def _assert_cli_guidance_recovers(output: str, repo: _Repo, tmp_path: Path) -> None:
    guidance = recovery_guidance(repo.project)
    assert guidance.state is RecoveryState.RESTORABLE
    for line in guidance.lines():
        assert _normalised(line) in _normalised(output)
    _execute(guidance, cwd=tmp_path)
    _assert_recovered(repo)


def test_cli_interrupted_after_git_mv_prints_guidance_that_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _prepare(monkeypatch)

    def _interrupt(*args: object, **kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(update_module, "apply_plan", _interrupt)

    result = runner.invoke(app, ["update", str(repo.project)])

    assert result.exit_code == 130, result.output
    assert "Cancelled." in result.output
    assert "R" in _git("status", "--porcelain", cwd=repo.root).split()[0]
    _assert_cli_guidance_recovers(result.output, repo, tmp_path)


def test_cli_failure_before_staging_prints_guidance_that_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _prepare(monkeypatch)

    def _relock(project: Path) -> str:
        raise UpdateError("uv exploded")

    monkeypatch.setattr(update_module, "relock", _relock)

    result = runner.invoke(app, ["update", str(repo.project)])

    assert result.exit_code == 1, result.output
    assert "uv exploded" in result.output
    _assert_cli_guidance_recovers(result.output, repo, tmp_path)


def test_cli_partial_stage_failure_prints_guidance_that_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _prepare(monkeypatch)
    monkeypatch.setattr(update_module, "relock", lambda project: None)
    monkeypatch.setattr(
        engine_module, "metadata_json", lambda metadata, degraded_reason=None: "{}\n"
    )

    def _stage_part_way(project: Path) -> None:
        _git("add", "mod.txt", cwd=project)
        raise UpdateError("`git add -A` failed part-way")

    monkeypatch.setattr(update_module, "stage_result", _stage_part_way)

    result = runner.invoke(app, ["update", str(repo.project)])

    assert result.exit_code == 1, result.output
    _assert_cli_guidance_recovers(result.output, repo, tmp_path)


def test_cli_engine_error_after_mutation_prints_guidance_that_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)
    _prepare(monkeypatch)
    monkeypatch.setattr(update_module, "relock", lambda project: None)
    boom = engine_module.ForgeEngineError.__new__(engine_module.ForgeEngineError)

    def _refresh(metadata: object, degraded_reason: object = None) -> str:
        raise boom

    monkeypatch.setattr(engine_module, "metadata_json", _refresh)
    monkeypatch.setattr(engine_module, "explain", lambda exc: "the engine said no")

    result = runner.invoke(app, ["update", str(repo.project)])

    assert result.exit_code == 1, result.output
    assert "the engine said no" in result.output
    _assert_cli_guidance_recovers(result.output, repo, tmp_path)


@pytest.mark.parametrize("extra", [[], ["--dry-run"]], ids=["real", "dry-run"])
def test_cli_failure_before_any_mutation_says_nothing_to_recover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    repo = _make_repo(tmp_path)

    def _malformed(project: Path) -> object:
        raise UpdateError("the recorded metadata is malformed")

    monkeypatch.setattr(pipeline_module, "prepare_update", _malformed)

    result = runner.invoke(app, ["update", str(repo.project), *extra])

    assert result.exit_code == 1, result.output
    text = _normalised(result.output)
    assert "the recorded metadata is malformed" in text
    assert "nothing to recover" in text
    assert "git restore" not in text
    _assert_recovered(repo)


def test_cli_dirty_tree_at_start_prints_no_recovery_command(
    tmp_path: Path,
) -> None:
    """The hazard: the user's OWN uncommitted work is what is dirty. The update
    never started, so no command that discards a working tree is theirs to run.
    """
    repo = _make_repo(tmp_path)
    notes = repo.project / "my-notes.txt"
    notes.write_bytes(b"work in progress\n")
    (repo.project / "mod.txt").write_bytes(b"my own edit\n")

    result = runner.invoke(app, ["update", str(repo.project)])

    assert result.exit_code == 1, result.output
    text = _normalised(result.output)
    assert "uncommitted changes" in text
    for fragment in ("git restore", "git clean", "nothing to recover", "-C"):
        assert fragment not in text
    assert notes.read_bytes() == b"work in progress\n"
    assert (repo.project / "mod.txt").read_bytes() == b"my own edit\n"


def test_cli_incompatible_engine_still_exits_3_without_recovery_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _make_repo(tmp_path)

    def _incompatible(project: Path) -> object:
        raise engine_module.EngineCompatibilityError("engine out of range")

    monkeypatch.setattr(pipeline_module, "prepare_update", _incompatible)

    result = runner.invoke(app, ["update", str(repo.project)])

    assert result.exit_code == 3, result.output
    assert "git restore" not in result.output
    assert "nothing to recover" not in result.output


def test_a_project_path_containing_markup_characters_prints_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rich must neither read `[...]` in a path as markup nor wrap the command."""
    repo = _make_repo(tmp_path / "with [brackets] and spaces")
    _prepare(monkeypatch)

    def _relock(project: Path) -> str:
        raise UpdateError("uv exploded")

    monkeypatch.setattr(update_module, "relock", _relock)

    result = runner.invoke(app, ["update", str(repo.project)])

    assert result.exit_code == 1, result.output
    guidance = recovery_guidance(repo.project)
    restore_line = guidance.lines()[1].strip()
    assert restore_line in result.output  # one unwrapped line, brackets intact
    _execute(guidance, cwd=tmp_path)
    _assert_recovered(repo)


@pytest.mark.parametrize("state", list(RecoveryState))
def test_no_guidance_ever_prints_the_retired_chained_command(
    state: RecoveryState,
) -> None:
    """`git restore . && git clean -fd` is what 0.4.0 printed. It recovers
    nothing once anything is staged and chains a delete behind a restore with
    no review step, so no state may print it again.
    """
    lines = RecoveryGuidance(state, Path("/repo"), has_untracked=True).lines()

    assert recovery_recipes.LEGACY_0_4_0_HINT not in " ".join(lines)
