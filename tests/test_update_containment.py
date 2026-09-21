"""CF-22.01 (#193, ADR 0052): every engine-update filesystem target is contained.

Real `git`, no network, no engine render -- the same fast-suite shape as
`tests/test_update_engine.py`, so this runs in the CI `test` matrix *and* the
`windows` job. The spelling rules are pure and host-independent by design, so
the table below is exercised identically on both; the symlink and junction
cases create real links and skip where the host will not allow one (an
unprivileged Windows account).

What is proven, against a real outside sentinel file:

- the accepted spelling, and every rejected class, on every host;
- an escaping target -- via a plan, a rename endpoint, the metadata filename,
  or a tampered recorded `output[].target` -- is refused with the sentinel
  neither read nor changed;
- the whole update is validated before its first mutation, so an invalid
  *late* target leaves no partial state;
- final symlinks, symlinked parents and Windows junctions that escape are
  refused, while a link that stays inside the project keeps working.

The installed-wheel half of this evidence is CF-22.03's.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from create_forge import paths
from create_forge.update import (
    UpdateError,
    apply_plan,
    apply_renames,
    degraded_plan,
    preflight_update,
    read_recorded,
    route_for,
    write_recorded,
)

METADATA_FILE = ".forge/generation.json"
SENTINEL_TEXT = b"outside sentinel -- must never be read, changed or removed\n"


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


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "--quiet", "--initial-branch=main", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "core.autocrlf", "false", cwd=path)


def _commit(path: Path) -> None:
    _git("add", "-A", cwd=path)
    _git("commit", "--quiet", "-m", "commit", cwd=path)


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


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
class _World:
    """A committed project plus an outside sentinel it must never reach."""

    project: Path
    outside: Path
    sentinel: Path


@pytest.fixture
def world(tmp_path: Path) -> _World:
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(SENTINEL_TEXT)
    _init_repo(project)
    (project / "a.txt").write_bytes(b"old a\n")
    (project / "keep.txt").write_bytes(b"keep\n")
    _commit(project)
    return _World(project=project, outside=outside, sentinel=sentinel)


def _assert_sentinel_untouched(world: _World) -> None:
    assert world.sentinel.read_bytes() == SENTINEL_TEXT
    assert sorted(p.name for p in world.outside.iterdir()) == ["sentinel.txt"]


def _reads_outside(reads: list[Path], world: _World) -> list[Path]:
    outside = world.outside.resolve()
    return [path for path in reads if outside in path.resolve().parents]


def _assert_project_unchanged(world: _World) -> None:
    assert _git("status", "--porcelain", cwd=world.project).strip() == ""


def _link(link: Path, target: Path, *, directory: bool) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this host")


def _junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("junctions are Windows-only")
    result = subprocess.run(  # noqa: S603
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],  # noqa: S607
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.skip("could not create a junction on this host")


# --------------------------------------------------------------------------- #
# The accepted spelling -- pure, identical on every host                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "target",
    [
        "src/pkg/module.py",
        "a",
        "a.b.c",
        ".forge/generation.json",
        ".github/workflows/ci.yml",
        "docs/aux-notes.md",  # `aux-notes` is not the reserved device `aux`
        "console.py",  # nor is `console` the device `con`
        "com10.txt",  # only COM1-COM9 are reserved
    ],
)
def test_the_accepted_spelling_is_relative_posix(target: str) -> None:
    assert paths.relative_parts(target) == tuple(target.split("/"))


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("", "empty or root-only"),
        (".", "a `.` path component"),
        ("./", "a `.` path component"),
        ("/", "empty or root-only"),
        ("//", "empty or root-only"),
        ("/etc/passwd", "absolute"),
        ("//server/share/x", "absolute"),
        ("C:/x", "a `:`"),
        ("C:x", "a `:`"),
        ("a/C:x", "a `:`"),
        ("stream.txt:hidden", "a `:`"),
        ("\\\\server\\share\\x", "a backslash"),
        ("a\\b", "a backslash"),
        ("C:\\Windows\\x", "a backslash"),
        ("../x", "a `..` path component"),
        ("a/../b", "a `..` path component"),
        ("a/./b", "a `.` path component"),
        ("a//b", "an empty path component"),
        ("a/", "an empty path component"),
        ("a\x00b", "a control character"),
        ("a\nb", "a control character"),
        ("a\x7fb", "a control character"),
        ("aux.py", "reserved device name"),
        ("AUX", "reserved device name"),
        ("src/con", "reserved device name"),
        ("nul.tar.gz", "reserved device name"),
        ("COM1", "reserved device name"),
        ("lpt9.txt", "reserved device name"),
        ("CONIN$", "reserved device name"),
        ("a./b", "ending in a dot or space"),
        ("a /b", "ending in a dot or space"),
        ("dir/file.", "ending in a dot or space"),
        ("dir/file ", "ending in a dot or space"),
    ],
)
def test_every_rejected_spelling_is_refused_on_every_host(
    target: str, reason: str
) -> None:
    with pytest.raises(paths.PathContainmentError, match=reason) as excinfo:
        paths.relative_parts(target)
    assert excinfo.value.violation is paths.Violation.SPELLING


@pytest.mark.parametrize(
    "target",
    [
        ".git/hooks/pre-commit",
        ".git/config",
        "sub/.git/hooks/pre-commit",
        "module.pyc",
        "src/__pycache__/module.cpython-313.pyc",
        "~draft.txt",
        ".DS_Store",
        "sub/.DS_Store",
    ],
)
def test_the_boundary_refuses_the_same_names_the_new_path_does(
    tmp_path: Path, target: str
) -> None:
    boundary = paths.ProjectBoundary.for_project(tmp_path)

    with pytest.raises(paths.PathContainmentError) as excinfo:
        boundary.resolve(target)

    assert excinfo.value.violation is paths.Violation.EXCLUDED


def test_the_boundary_returns_the_lexical_location_under_the_real_root(
    tmp_path: Path,
) -> None:
    boundary = paths.ProjectBoundary.for_project(tmp_path)

    resolved = boundary.resolve("src/pkg/new_module.py")  # leaf does not exist yet

    assert resolved == boundary.root / "src" / "pkg" / "new_module.py"


@pytest.mark.parametrize("failure", [OSError("denied"), RuntimeError("Symlink loop")])
def test_a_path_that_cannot_be_resolved_is_refused_not_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    """A symlink loop or an unreadable component is not provably inside."""
    boundary = paths.ProjectBoundary.for_project(tmp_path)
    real_resolve = Path.resolve

    def _resolve(self: Path, strict: bool = False) -> Path:
        if self.name == "loop":
            raise failure
        return real_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", _resolve)

    with pytest.raises(paths.PathContainmentError) as excinfo:
        boundary.resolve("a/loop")

    assert excinfo.value.violation is paths.Violation.ESCAPE


def test_the_error_names_the_target_and_rule_but_no_filesystem_path(
    tmp_path: Path,
) -> None:
    boundary = paths.ProjectBoundary.for_project(tmp_path)

    with pytest.raises(paths.PathContainmentError) as excinfo:
        boundary.resolve("../secret")

    assert str(tmp_path) not in str(excinfo.value)
    assert "'../secret'" in str(excinfo.value)


def test_resolve_all_raises_before_returning_anything(tmp_path: Path) -> None:
    boundary = paths.ProjectBoundary.for_project(tmp_path)

    with pytest.raises(paths.PathContainmentError):
        boundary.resolve_all(["fine.txt", "also/fine.txt", "../not-fine.txt"])

    assert boundary.resolve_all(["fine.txt", "also/fine.txt"]).keys() == {
        "fine.txt",
        "also/fine.txt",
    }


# --------------------------------------------------------------------------- #
# Symlinks and junctions                                                       #
# --------------------------------------------------------------------------- #


def test_an_escaping_final_symlink_is_refused(world: _World) -> None:
    _link(world.project / "link.txt", world.sentinel, directory=False)
    boundary = paths.ProjectBoundary.for_project(world.project)

    with pytest.raises(paths.PathContainmentError) as excinfo:
        boundary.resolve("link.txt")

    assert excinfo.value.violation is paths.Violation.ESCAPE


def test_a_symlinked_parent_that_escapes_is_refused_even_for_a_new_leaf(
    world: _World,
) -> None:
    _link(world.project / "pkg", world.outside, directory=True)
    boundary = paths.ProjectBoundary.for_project(world.project)

    with pytest.raises(paths.PathContainmentError) as excinfo:
        boundary.resolve("pkg/brand_new.py")  # the leaf does not exist anywhere

    assert excinfo.value.violation is paths.Violation.ESCAPE


def test_a_windows_junction_that_escapes_is_refused(world: _World) -> None:
    _junction(world.project / "pkg", world.outside)
    boundary = paths.ProjectBoundary.for_project(world.project)

    with pytest.raises(paths.PathContainmentError) as excinfo:
        boundary.resolve("pkg/sentinel.txt")

    assert excinfo.value.violation is paths.Violation.ESCAPE


def test_a_symlink_that_stays_inside_the_project_keeps_working(world: _World) -> None:
    """A user's own internal link is a legitimate local edit (AC-05)."""
    _link(world.project / "alias.txt", world.project / "a.txt", directory=False)
    boundary = paths.ProjectBoundary.for_project(world.project)

    assert boundary.resolve("alias.txt") == boundary.root / "alias.txt"


def test_removing_an_internal_symlink_target_removes_the_link_not_what_it_points_at(
    world: _World,
) -> None:
    _link(world.project / "alias.txt", world.project / "a.txt", directory=False)

    outcome = apply_plan(
        world.project,
        [_Target("alias.txt", "removed")],
        [],
        old={"alias.txt": b"old a\n"},
        new={},
        dry_run=False,
    )

    assert outcome.results[0].status == "clean"
    assert not (world.project / "alias.txt").is_symlink()
    assert (world.project / "a.txt").read_bytes() == b"old a\n"


@pytest.mark.parametrize("dry_run", [False, True])
def test_a_plan_target_through_an_escaping_symlink_never_touches_the_sentinel(
    world: _World, dry_run: bool
) -> None:
    _link(world.project / "link.txt", world.sentinel, directory=False)

    with pytest.raises(UpdateError, match="resolves outside the project"):
        apply_plan(
            world.project,
            [_Target("link.txt", "changed")],
            [],
            old={"link.txt": SENTINEL_TEXT},
            new={"link.txt": b"overwritten\n"},
            dry_run=dry_run,
        )

    _assert_sentinel_untouched(world)


@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_a_new_file_under_an_escaping_linked_parent_writes_nothing_outside(
    world: _World, kind: str
) -> None:
    if kind == "junction":
        _junction(world.project / "pkg", world.outside)
    else:
        _link(world.project / "pkg", world.outside, directory=True)

    with pytest.raises(UpdateError, match="resolves outside the project"):
        apply_plan(
            world.project,
            [_Target("pkg/mod.py", "added")],
            [],
            old={},
            new={"pkg/mod.py": b"print('x')\n"},
            dry_run=False,
        )

    _assert_sentinel_untouched(world)


# --------------------------------------------------------------------------- #
# apply_plan: escapes, ordering, dry-run                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_target",
    [
        "../outside/sentinel.txt",
        "sub/../../outside/sentinel.txt",
        "/etc/passwd",
        "C:x",
        "a\\b",
        "aux.py",
        ".git/hooks/pre-commit",
    ],
)
@pytest.mark.parametrize("classification", ["added", "changed", "removed", "renamed"])
def test_apply_plan_refuses_every_bad_target_and_leaves_the_sentinel_alone(
    world: _World, bad_target: str, classification: str
) -> None:
    with pytest.raises(UpdateError, match="unsafe update target"):
        apply_plan(
            world.project,
            [_Target(bad_target, classification)],
            [],
            old={bad_target: SENTINEL_TEXT},
            new={bad_target: b"new\n"},
            dry_run=False,
        )

    _assert_sentinel_untouched(world)
    _assert_project_unchanged(world)


@pytest.mark.parametrize(
    "target",
    [
        _Target("../outside/sentinel.txt", "unchanged"),
        _Target("../outside/sentinel.txt", "changed", "skip-if-exists"),
    ],
    ids=["unchanged", "skip-if-exists"],
)
def test_apply_plan_validates_entries_it_would_never_write(
    world: _World, target: _Target
) -> None:
    """A skipped or unchanged entry is still a provider-supplied string."""
    with pytest.raises(UpdateError, match="unsafe update target"):
        apply_plan(world.project, [target], [], old={}, new={}, dry_run=False)


def test_an_invalid_late_target_leaves_no_partial_mutation(world: _World) -> None:
    """`a.txt` is pristine and would be rewritten; the bad target sorts after it.

    If validation were per-target, `a.txt` would already be replaced by the
    time the bad entry was reached.
    """
    plan = [
        _Target("a.txt", "changed"),
        _Target("keep.txt", "removed"),
        _Target("zz/../../outside/sentinel.txt", "changed"),
    ]

    with pytest.raises(UpdateError, match="unsafe update target"):
        apply_plan(
            world.project,
            plan,
            [],
            old={"a.txt": b"old a\n", "keep.txt": b"keep\n"},
            new={"a.txt": b"new a\n"},
            dry_run=False,
        )

    assert (world.project / "a.txt").read_bytes() == b"old a\n"
    assert (world.project / "keep.txt").exists()
    _assert_project_unchanged(world)
    _assert_sentinel_untouched(world)


def test_dry_run_reads_nothing_outside_the_project(
    world: _World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`dry_run` only ever gated writes; the reads above them are what mattered."""
    reads: list[Path] = []
    real_read_bytes = Path.read_bytes

    def _spy(self: Path) -> bytes:
        reads.append(self)
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _spy)

    with pytest.raises(UpdateError):
        apply_plan(
            world.project,
            [_Target("../outside/sentinel.txt", "changed")],
            [],
            old={"../outside/sentinel.txt": SENTINEL_TEXT},
            new={"../outside/sentinel.txt": b"new\n"},
            dry_run=True,
        )

    assert _reads_outside(reads, world) == []


# --------------------------------------------------------------------------- #
# Tampered recorded metadata -- the least trusted strings in an update         #
# --------------------------------------------------------------------------- #


def _write_tampered_document(world: _World, *, target: str, digest: str) -> None:
    document = {
        "provider": {"version": "0.6.0"},
        "spec": {},
        "output": [{"target": target, "digest": digest}],
    }
    path = world.project / METADATA_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


@pytest.mark.parametrize("dry_run", [False, True])
def test_a_tampered_recorded_target_cannot_reach_the_sentinel(
    world: _World, dry_run: bool
) -> None:
    """The dangerous case: the recorded digest *matches* the outside file.

    Before ADR 0052 the degraded removal loop read the outside file, saw the
    digest match, and deleted it -- and the read happened in `--dry-run` too.
    """
    _write_tampered_document(
        world, target="../outside/sentinel.txt", digest=_digest(SENTINEL_TEXT)
    )
    _commit(world.project)
    recorded = read_recorded(world.project, metadata_filename=METADATA_FILE)

    with pytest.raises(UpdateError, match="unsafe update target"):
        degraded_plan(
            world.project,
            {"a.txt": b"new a\n"},
            recorded_digests=recorded.digests,
            dry_run=dry_run,
        )

    _assert_sentinel_untouched(world)
    assert (world.project / "a.txt").read_bytes() == b"old a\n"
    _assert_project_unchanged(world)


def test_a_tampered_recorded_target_is_not_read_in_a_dry_run(
    world: _World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_tampered_document(
        world, target="../outside/sentinel.txt", digest=_digest(SENTINEL_TEXT)
    )
    _commit(world.project)
    recorded = read_recorded(world.project, metadata_filename=METADATA_FILE)
    reads: list[Path] = []
    real_read_bytes = Path.read_bytes

    def _spy(self: Path) -> bytes:
        reads.append(self)
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _spy)

    with pytest.raises(UpdateError):
        degraded_plan(
            world.project, {}, recorded_digests=recorded.digests, dry_run=True
        )

    assert _reads_outside(reads, world) == []


def test_a_tampered_recorded_git_hook_target_is_refused(world: _World) -> None:
    _write_tampered_document(
        world, target=".git/hooks/pre-commit", digest=_digest(b"#!/bin/sh\n")
    )
    recorded = read_recorded(world.project, metadata_filename=METADATA_FILE)

    with pytest.raises(UpdateError, match="excluded target"):
        degraded_plan(
            world.project, {}, recorded_digests=recorded.digests, dry_run=False
        )


def test_a_bad_new_render_target_is_refused_before_a_degraded_update_writes(
    world: _World,
) -> None:
    with pytest.raises(UpdateError, match="unsafe update target"):
        degraded_plan(
            world.project,
            {"a.txt": b"new a\n", "zz/../../escape.txt": b"x"},
            recorded_digests={"a.txt": _digest(b"old a\n")},
            dry_run=False,
        )

    assert (world.project / "a.txt").read_bytes() == b"old a\n"
    _assert_project_unchanged(world)


# --------------------------------------------------------------------------- #
# Renames                                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "rename",
    [
        _Rename("c", "a.txt", "../outside/moved.txt"),
        _Rename("c", "../outside/sentinel.txt", "moved.txt"),
        _Rename("c", "a.txt", "/tmp/moved.txt"),  # noqa: S108
        _Rename("c", "a.txt", ".git/hooks/pre-commit"),
    ],
    ids=["escaping-destination", "escaping-source", "absolute", "git-hook"],
)
def test_apply_renames_refuses_an_unsafe_endpoint(
    world: _World, rename: _Rename
) -> None:
    with pytest.raises(UpdateError, match="unsafe update target"):
        apply_renames(world.project, [rename])

    _assert_sentinel_untouched(world)
    assert (world.project / "a.txt").exists()
    _assert_project_unchanged(world)


def test_a_valid_rename_is_not_applied_when_a_later_one_is_unsafe(
    world: _World,
) -> None:
    renames = [
        _Rename("c", "a.txt", "moved.txt"),
        _Rename("c", "keep.txt", "../outside/keep.txt"),
    ]

    with pytest.raises(UpdateError, match="unsafe update target"):
        apply_renames(world.project, renames)

    assert (world.project / "a.txt").exists()
    assert not (world.project / "moved.txt").exists()
    _assert_project_unchanged(world)


def test_apply_renames_treats_a_leading_dash_as_a_path_not_an_option(
    world: _World,
) -> None:
    """Without `--`, `git mv` reads `-dash.txt` as a switch, fails, and the
    `shutil.move` fallback moves the file without staging the rename. The
    index recording a rename is what tells the two apart.
    """
    (world.project / "-dash.txt").write_bytes(b"dash\n")
    _commit(world.project)

    apply_renames(world.project, [_Rename("c", "-dash.txt", "dest.txt")])

    assert (world.project / "dest.txt").read_bytes() == b"dash\n"
    assert not (world.project / "-dash.txt").exists()
    status = _git("status", "--porcelain", cwd=world.project)
    assert "R" in status.split()[0], status


def test_a_legitimate_rename_still_carries_a_local_edit(world: _World) -> None:
    (world.project / "a.txt").write_bytes(b"locally edited\n")

    apply_renames(world.project, [_Rename("c", "a.txt", "sub/moved.txt")])

    assert (world.project / "sub" / "moved.txt").read_bytes() == b"locally edited\n"
    assert not (world.project / "a.txt").exists()


# --------------------------------------------------------------------------- #
# The metadata filename and preflight                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("filename", ["../generation.json", "/abs.json", "a\\b.json"])
def test_the_metadata_filename_is_contained_on_every_access(
    world: _World, filename: str
) -> None:
    with pytest.raises(UpdateError, match="unsafe update target"):
        read_recorded(world.project, metadata_filename=filename)
    with pytest.raises(UpdateError, match="unsafe update target"):
        write_recorded(world.project, metadata_filename=filename, content="x")
    with pytest.raises(UpdateError, match="unsafe update target"):
        route_for(world.project, metadata_filename=filename, legacy=False)


def test_a_metadata_directory_symlinked_outside_is_refused(world: _World) -> None:
    (world.outside / "generation.json").write_text("{}", encoding="utf-8")
    _link(world.project / ".forge", world.outside, directory=True)

    with pytest.raises(UpdateError, match="resolves outside the project"):
        read_recorded(world.project, metadata_filename=METADATA_FILE)
    with pytest.raises(UpdateError, match="resolves outside the project"):
        write_recorded(world.project, metadata_filename=METADATA_FILE, content="{}")


def test_write_recorded_writes_a_contained_metadata_file(world: _World) -> None:
    (world.project / ".forge").mkdir()

    write_recorded(world.project, metadata_filename=METADATA_FILE, content="{}\n")

    assert (world.project / METADATA_FILE).read_text(encoding="utf-8") == "{}\n"


def test_preflight_accepts_a_fully_valid_update(world: _World) -> None:
    preflight_update(
        world.project,
        metadata_filename=METADATA_FILE,
        targets=["a.txt", "src/new.py"],
        renames=[_Rename("c", "a.txt", "b.txt")],
        recorded_targets=["a.txt"],
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"metadata_filename": "../generation.json"},
        {"targets": ["ok.txt", "../escape.txt"]},
        {"renames": [_Rename("c", "a.txt", "../escape.txt")]},
        {"renames": [_Rename("c", "../escape.txt", "b.txt")]},
        {"recorded_targets": ["ok.txt", "/abs.txt"]},
    ],
    ids=["metadata", "target", "rename-to", "rename-from", "recorded"],
)
def test_preflight_rejects_a_bad_string_in_any_position(
    world: _World, kwargs: dict[str, Any]
) -> None:
    arguments: dict[str, Any] = {"metadata_filename": METADATA_FILE, **kwargs}

    with pytest.raises(UpdateError, match="unsafe update target"):
        preflight_update(world.project, **arguments)


def test_preflight_touches_nothing(world: _World) -> None:
    with pytest.raises(UpdateError):
        preflight_update(
            world.project,
            metadata_filename=METADATA_FILE,
            targets=["a.txt", "../escape.txt"],
        )

    _assert_project_unchanged(world)
    _assert_sentinel_untouched(world)


# --------------------------------------------------------------------------- #
# Ordinary behaviour is preserved                                              #
# --------------------------------------------------------------------------- #


def test_a_normal_update_still_merges_a_local_edit_inside_the_boundary(
    world: _World,
) -> None:
    (world.project / "a.txt").write_bytes(b"old a\nlocal line\n")
    _commit(world.project)

    outcome = apply_plan(
        world.project,
        [_Target("a.txt", "changed")],
        [],
        old={"a.txt": b"old a\n"},
        new={"a.txt": b"new first\nold a\n"},
        dry_run=False,
    )

    assert outcome.results[0].status == "clean"
    assert (world.project / "a.txt").read_bytes() == b"new first\nold a\nlocal line\n"
    _assert_sentinel_untouched(world)
