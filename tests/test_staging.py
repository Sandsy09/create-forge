"""`create_forge.staging` -- destination conflicts, target safety, staging
placement, atomic finalisation, and cleanup after failure (ADR 0015).

No engine dependency: this module is deliberately engine-free, so these
tests run in the fast suite with no optional `engine` extra (ADR 0018)
installed.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from create_forge.staging import (
    DestinationConflictError,
    StagingError,
    discard_on_failure,
    ensure_available,
    staged,
    write_files,
)


def test_ensure_available_accepts_a_missing_destination(tmp_path: Path) -> None:
    ensure_available(tmp_path / "proj")  # does not raise


def test_ensure_available_accepts_an_existing_empty_destination(
    tmp_path: Path,
) -> None:
    dst = tmp_path / "proj"
    dst.mkdir()
    ensure_available(dst)  # does not raise


def test_ensure_available_rejects_a_non_empty_destination(tmp_path: Path) -> None:
    dst = tmp_path / "proj"
    dst.mkdir()
    (dst / "existing.txt").write_text("hi", encoding="utf-8")

    with pytest.raises(DestinationConflictError, match="already exists"):
        ensure_available(dst)


def test_write_files_translates_an_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()

    def failing_write_bytes(self: Path, _content: bytes) -> int:
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(Path, "write_bytes", failing_write_bytes)

    with pytest.raises(StagingError, match="could not write"):
        write_files(root, [("file.txt", b"data")])


def test_write_files_creates_nested_targets_and_parents(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    write_files(
        root,
        [
            ("pyproject.toml", b"[project]\n"),
            ("src/pkg/__init__.py", b""),
            ("src/pkg/module.py", b"print('hi')\n"),
        ],
    )

    assert (root / "pyproject.toml").read_bytes() == b"[project]\n"
    assert (root / "src" / "pkg" / "__init__.py").exists()
    assert (root / "src" / "pkg" / "module.py").read_bytes() == b"print('hi')\n"


@pytest.mark.parametrize(
    "target",
    [
        "../escape.txt",
        "sub/../../escape.txt",
        "/etc/passwd",
    ],
)
def test_write_files_refuses_targets_that_escape_the_root(
    tmp_path: Path, target: str
) -> None:
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(StagingError, match="refusing to write"):
        write_files(root, [(target, b"data")])

    # Nothing from the batch is written, and nothing escaped the root.
    assert list(root.iterdir()) == []
    assert not (tmp_path / "escape.txt").exists()


def test_staged_creates_the_directory_adjacent_to_the_destination(
    tmp_path: Path,
) -> None:
    dst = tmp_path / "nested" / "proj"

    with staged(dst) as staging_dir:
        assert staging_dir.parent == dst.parent
        assert staging_dir != dst
        write_files(staging_dir, [("pyproject.toml", b"[project]\n")])

    assert dst.is_dir()
    assert (dst / "pyproject.toml").read_bytes() == b"[project]\n"
    # The staging directory itself is gone -- renamed, not copied.
    assert not staging_dir.exists()


def test_staged_replaces_an_existing_empty_destination(tmp_path: Path) -> None:
    dst = tmp_path / "proj"
    dst.mkdir()

    with staged(dst) as staging_dir:
        write_files(staging_dir, [("marker.txt", b"x")])

    assert (dst / "marker.txt").read_bytes() == b"x"


def test_staged_translates_a_rename_failure_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "proj"

    def failing_rename(self: Path, _target: Path) -> Path:
        raise OSError("cross-device link (simulated)")

    monkeypatch.setattr(Path, "rename", failing_rename)

    with (
        pytest.raises(StagingError, match="could not move"),
        staged(dst) as staging_dir,
    ):
        write_files(staging_dir, [("marker.txt", b"x")])

    assert not dst.exists()
    assert not staging_dir.exists()


def test_staged_rejects_a_non_empty_destination_before_creating_anything(
    tmp_path: Path,
) -> None:
    dst = tmp_path / "proj"
    dst.mkdir()
    (dst / "existing.txt").write_text("hi", encoding="utf-8")

    before = set(tmp_path.iterdir())
    with pytest.raises(DestinationConflictError), staged(dst):
        raise AssertionError("body must not run for a non-empty destination")

    # No staging directory was left behind alongside dst.
    assert set(tmp_path.iterdir()) == before


def test_staged_removes_the_staging_tree_on_failure_and_leaves_no_destination(
    tmp_path: Path,
) -> None:
    dst = tmp_path / "proj"

    with pytest.raises(RuntimeError, match="boom"), staged(dst) as staging_dir:
        write_files(staging_dir, [("partial.txt", b"x")])
        raise RuntimeError("boom")

    assert not dst.exists()
    assert not staging_dir.exists()
    # Nothing but the (now-removed) staging directory was ever created next
    # to dst.
    assert list(tmp_path.iterdir()) == []


def test_staged_cleans_up_read_only_files_on_failure(tmp_path: Path) -> None:
    dst = tmp_path / "proj"

    with pytest.raises(RuntimeError), staged(dst) as staging_dir:
        write_files(staging_dir, [("locked.txt", b"x")])
        (staging_dir / "locked.txt").chmod(stat.S_IREAD)
        raise RuntimeError("boom")

    assert not staging_dir.exists()


def test_discard_on_failure_removes_a_destination_it_created(tmp_path: Path) -> None:
    dst = tmp_path / "proj"

    with pytest.raises(RuntimeError, match="boom"), discard_on_failure(dst):
        dst.mkdir()
        (dst / "partial.txt").write_text("x", encoding="utf-8")
        raise RuntimeError("boom")

    assert not dst.exists()


def test_discard_on_failure_leaves_a_pre_existing_destination_untouched(
    tmp_path: Path,
) -> None:
    dst = tmp_path / "proj"
    dst.mkdir()
    (dst / "already-here.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(RuntimeError, match="boom"), discard_on_failure(dst):
        raise RuntimeError("boom")

    assert dst.is_dir()
    assert (dst / "already-here.txt").read_text(encoding="utf-8") == "keep me"


def test_discard_on_failure_tolerates_a_failure_before_anything_was_created(
    tmp_path: Path,
) -> None:
    """A failure before `dst` is ever created (e.g. the render itself fails)
    must not error on cleanup just because there is nothing to remove.
    """
    dst = tmp_path / "proj"

    with pytest.raises(RuntimeError, match="boom"), discard_on_failure(dst):
        raise RuntimeError("boom")

    assert not dst.exists()


def test_discard_on_failure_does_nothing_on_success(tmp_path: Path) -> None:
    dst = tmp_path / "proj"

    with discard_on_failure(dst):
        dst.mkdir()
        (dst / "file.txt").write_text("x", encoding="utf-8")

    assert (dst / "file.txt").read_text(encoding="utf-8") == "x"


def test_discard_on_failure_removes_read_only_files_it_created(
    tmp_path: Path,
) -> None:
    dst = tmp_path / "proj"

    with pytest.raises(RuntimeError), discard_on_failure(dst):
        dst.mkdir()
        locked = dst / "locked.txt"
        locked.write_text("x", encoding="utf-8")
        locked.chmod(stat.S_IREAD)
        raise RuntimeError("boom")

    assert not dst.exists()


@pytest.mark.skipif(os.name != "nt", reason="drive-qualified paths are Windows-only")
@pytest.mark.parametrize("target", ["D:evil.txt", "C:\\Windows\\escape.txt"])
def test_write_files_refuses_a_drive_qualified_target_on_windows(
    tmp_path: Path, target: str
) -> None:
    """A target with a backslash or drive letter is only meaningfully an
    escape on Windows, where `pathlib.Path` (unlike the `PurePosixPath` used
    to classify the target) treats both as path structure. On POSIX, such a
    target is just an odd literal filename that stays under the staging
    root -- there is nothing to escape to.
    """
    root = tmp_path / "root"
    root.mkdir()

    with pytest.raises(StagingError, match="refusing to write"):
        write_files(root, [(target, b"data")])
