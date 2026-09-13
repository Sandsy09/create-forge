"""`create_forge.lifecycle` -- the engine `new` path's post-rename Git and
pre-commit lifecycle (ADR 0041, ADR 0045).

Engine-free, like `test_staging.py`: these tests run in the fast suite with
no optional `engine` extra installed, and never invoke a real `git` or `uv`
subprocess -- every case monkeypatches `subprocess.run`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from create_forge.lifecycle import finalise_project

_INIT = ["init", "--initial-branch=main"]
_ADD = ["add", "-A"]
_COMMIT = ["commit", "--no-verify", "-m", "feat: initial scaffold from template"]
_HOOKS_MARKER = "pre-commit"


def _ok(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, 0, "", "")


def _fail(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, 1, "", "")


def _record(
    monkeypatch: pytest.MonkeyPatch, calls: list[list[str]], failing: set[str]
) -> None:
    """Route every `subprocess.run` call by its first argument (`git`/`uv`),
    recording the full argv and failing the ones named in `failing`.
    """

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        key = command[0] if command[0] != "uv" else _HOOKS_MARKER
        return _fail(command) if key in failing else _ok(command)

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_runs_git_init_add_commit_with_no_hooks_when_no_config_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    _record(monkeypatch, calls, failing=set())

    warnings = finalise_project(tmp_path)

    assert warnings == ()
    assert calls == [["git", *_INIT], ["git", *_ADD], ["git", *_COMMIT]]


def test_installs_hooks_only_when_pre_commit_config_was_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    calls: list[list[str]] = []
    _record(monkeypatch, calls, failing=set())

    warnings = finalise_project(tmp_path)

    assert warnings == ()
    assert calls[:3] == [["git", *_INIT], ["git", *_ADD], ["git", *_COMMIT]]
    assert calls[3] == [
        "uv",
        "run",
        "--directory",
        str(tmp_path),
        "pre-commit",
        "install",
        "--install-hooks",
    ]


def test_a_git_init_failure_skips_every_later_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    calls: list[list[str]] = []
    _record(monkeypatch, calls, failing={"git"})

    warnings = finalise_project(tmp_path)

    assert calls == [["git", *_INIT]]
    assert len(warnings) == 1
    assert f"git -C {tmp_path} init --initial-branch=main" in warnings[0]


def test_a_git_add_failure_skips_the_commit_but_still_tries_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[:2] == ["git", "add"]:
            return _fail(command)
        return _ok(command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    warnings = finalise_project(tmp_path)

    assert calls == [
        ["git", *_INIT],
        ["git", *_ADD],
        [
            "uv",
            "run",
            "--directory",
            str(tmp_path),
            "pre-commit",
            "install",
            "--install-hooks",
        ],
    ]
    assert len(warnings) == 1
    assert "git add -A" in warnings[0]


def test_a_commit_failure_still_tries_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[:2] == ["git", "commit"]:
            return _fail(command)
        return _ok(command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    warnings = finalise_project(tmp_path)

    assert calls[-1][0] == "uv"
    assert len(warnings) == 1
    assert "git commit" in warnings[0]


def test_reports_a_missing_git_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", missing)

    warnings = finalise_project(tmp_path)

    assert len(warnings) == 1
    assert "git is not on PATH" in warnings[0]


def test_reports_a_missing_uv_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "uv":
            raise FileNotFoundError("uv")
        return _ok(command)

    monkeypatch.setattr(subprocess, "run", fake_run)

    warnings = finalise_project(tmp_path)

    assert len(warnings) == 1
    assert "uv is not on PATH" in warnings[0]
    assert "uv>=0.12,<0.13" in warnings[0]


def test_never_raises_and_never_echoes_raw_subprocess_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, 1, "token=secret", "index-password=secret"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    warnings = finalise_project(tmp_path)  # must not raise

    assert len(warnings) == 1
    assert "secret" not in warnings[0]


def test_finish_it_yourself_hint_names_the_exact_manual_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    _record(monkeypatch, calls, failing={"git"})

    warnings = finalise_project(tmp_path)

    assert warnings[0].endswith(
        f"finish it yourself: git -C {tmp_path} init --initial-branch=main"
    )
