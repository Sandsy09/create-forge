"""Installed update-safety evidence (CF-22.03, ADR 0054): CF-22.01's containment
and CF-22.02's recovery, proven through the built wheel's console script paired
with the published `forge-template`.

`tests/test_update_containment.py` and `tests/test_update_recovery.py` prove both
fixes against `create_forge.update`'s own functions. Nothing there proves the
*shipped* console -- the wheel a user installs, the engine PyPI serves, the
process boundary. This does, with real repositories, a real generated project,
and an outside sentinel file no update may touch.

Two techniques make the installed console produce what it otherwise never would
offline (with the recorded provider equal to the installed one every target
classifies `unchanged`, and there is no way to inject a failure):

- **A genuinely changed update.** `update --degraded` decides "pristine" from the
  recorded per-target digest in the committed `.forge/generation.json`. Editing
  that file so a locally edited file's digest matches it, adding a recorded
  entry for a file the template no longer renders, and deleting a generated file
  gives a real changed, removed and added target -- staged by the real `git add
  -A`. It depends only on the `output[].target`/`digest` shape
  `update.read_recorded` already parses; a provider format change fails these
  tests loudly.
- **A real interruption.** A pre-existing `.git/index.lock` makes the real
  `git add -A` fail after every file has been written, leaving the unstaged,
  half-finished state an interrupted update leaves. The lock is removed before
  the printed recovery runs, as an interruption would have released it.

Not covered installed, and recorded as such in
`docs/update-safety-validation.md`: the normal route's real three-way *merge*
(it needs an older provider render that differs -- `tests/test_update_engine.py`
proves it) and renames (no shipped template declares one; see #209).

Runs on Linux and Windows CI; the symlinked-parent case is POSIX-only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.installed_client import (
    CLIENT_VERSION,
    ENGINE_VERSION,
    InstalledClient,
    assert_success,
    file_bytes,
    run,
)
from tests.recovery_recipes import CLEAN_ARGV, CLEAN_PREVIEW_ARGV, RESTORE_ARGV

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.e2e

METADATA = ".forge/generation.json"
SENTINEL = b"outside the project -- must never be read, changed or removed\n"
USER_DATA = b"owned by the user\n"
_OUTSIDE_TARGET = "../outside/sentinel.txt"

_LIBRARY_ANSWERS = {
    "project_description": "create-forge installed update-safety CF-22.03.",
    "license": "mit",
    "author_name": "create-forge e2e",
    "author_email": "create-forge-e2e@example.invalid",
}


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #


def _git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        timeout=60,
    )
    return completed.stdout.decode("utf-8", errors="replace")


def _new_args(dest: Path) -> list[str]:
    args = [
        "new",
        "Update Safety Trial",
        "--archetype",
        "library",
        "--yes",
        "--path",
        str(dest),
    ]
    for key, value in _LIBRARY_ANSWERS.items():
        args += ["--data", f"{key}={value}"]
    return args


def _sha(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _commit_all(project: Path, message: str) -> None:
    _git("add", "-A", cwd=project)
    _git("commit", "--quiet", "-m", message, cwd=project)


@dataclass(frozen=True, slots=True)
class State:
    """Everything an update could change about a project, for exact comparison."""

    files: dict[str, bytes]
    index: str
    status: str
    head: str


def _state(project: Path) -> State:
    return State(
        files=file_bytes(project),
        index=_git("ls-files", "-s", cwd=project),
        status=_git("status", "--porcelain", cwd=project),
        head=_git("rev-parse", "HEAD", cwd=project).strip(),
    )


@dataclass(frozen=True, slots=True)
class Scenario:
    """One copy of the generated project, and an outside directory beside it."""

    client: InstalledClient
    project: Path
    outside: Path

    @property
    def sentinel(self) -> Path:
        return self.outside / "sentinel.txt"

    def update(self, *flags: str) -> subprocess.CompletedProcess[str]:
        return run(
            [str(self.client.console), "update", *flags, str(self.project)],
            self.project,
            env=self.client.env,
        )

    def assert_sentinel_untouched(self) -> None:
        assert self.sentinel.read_bytes() == SENTINEL
        assert file_bytes(self.outside) == {"sentinel.txt": SENTINEL}


def _text(result: subprocess.CompletedProcess[str]) -> str:
    """Both streams, whitespace-normalised (Rich wraps long lines)."""
    return " ".join(f"{result.stdout} {result.stderr}".split())


def _doctor(project: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    """Rewrite the committed recorded document, as a user or repository could."""
    path = project / METADATA
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    # Bytes, not `write_text`: on Windows `write_text` would turn every `\n` into
    # `\r\n`, and the generated project's `.gitattributes` (`eol=lf`) would then
    # restore a different file than the one committed.
    path.write_bytes((json.dumps(document, indent=2) + "\n").encode("utf-8"))


def _outputs(document: dict[str, object]) -> list[dict[str, str]]:
    output = document["output"]
    assert isinstance(output, list)
    return output


def _recorded_targets(project: Path) -> list[str]:
    document = json.loads((project / METADATA).read_text(encoding="utf-8"))
    return [entry["target"] for entry in _outputs(document)]


def _record_digest(target: str, digest: str) -> Callable[[dict[str, object]], None]:
    def mutate(document: dict[str, object]) -> None:
        matching = [e for e in _outputs(document) if e["target"] == target]
        assert matching, f"{target!r} is not a recorded output"
        matching[0]["digest"] = digest

    return mutate


def _record_entry(target: str, digest: str) -> Callable[[dict[str, object]], None]:
    def mutate(document: dict[str, object]) -> None:
        # Every field the provider's document schema requires, so that a refusal
        # is about the *target*, not about a malformed entry.
        _outputs(document).append(
            {
                "target": target,
                "digest": digest,
                "owner": "foundation",
                "regeneration": "replace",
            }
        )

    return mutate


@dataclass(frozen=True, slots=True)
class Arranged:
    """A committed project with one changed, one removed and one added target
    pending for `update --degraded`, and the state to recover to.
    """

    readme_original: bytes
    readme_edited: bytes
    added_target: str
    added_original: bytes
    baseline: State
    user_file: Path


def _arrange_pending_changes(scenario: Scenario) -> Arranged:
    project = scenario.project
    readme = project / "README.md"
    readme_original = readme.read_bytes()
    readme_edited = readme_original + b"\nlocal edit\n"
    readme.write_bytes(readme_edited)

    (project / "obsolete.txt").write_bytes(b"no longer rendered\n")

    # A plain root file that nothing else depends on. Not `.gitignore` or
    # `.gitattributes`: deleting those changes how Git treats every other file
    # in the arrangement below.
    candidates = sorted(
        target
        for target in _recorded_targets(project)
        if "/" not in target
        and target
        not in {
            "README.md",
            "pyproject.toml",
            "uv.lock",
            ".gitignore",
            ".gitattributes",
            ".python-version",
        }
        and not target.startswith(".forge")
    )
    assert candidates, "the generated project has no plain root file to re-add"
    added_target = ".editorconfig" if ".editorconfig" in candidates else candidates[0]
    added_original = (project / added_target).read_bytes()
    (project / added_target).unlink()

    _doctor(project, _record_digest("README.md", _sha(readme_edited)))
    _doctor(project, _record_entry("obsolete.txt", _sha(b"no longer rendered\n")))

    user_file = project / "__pycache__" / "user-data.pyc"
    user_file.parent.mkdir(exist_ok=True)
    user_file.write_bytes(USER_DATA)
    _git("check-ignore", "-q", "__pycache__/user-data.pyc", cwd=project)  # precondition

    _commit_all(project, "arrange pending update")
    return Arranged(
        readme_original=readme_original,
        readme_edited=readme_edited,
        added_target=added_target,
        added_original=added_original,
        baseline=_state(project),
        user_file=user_file,
    )


# --------------------------------------------------------------------------- #
# fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def baseline(
    installed_client: InstalledClient, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """One project generated by the installed console, copied per scenario.

    A library with no capabilities has no `.venv` and nothing path-baked, so a
    copy is a faithful starting point and each scenario stays cheap.
    """
    dest = tmp_path_factory.mktemp("update-safety-baseline") / "project"
    generated = run(
        [str(installed_client.console), *_new_args(dest)],
        dest.parent,
        env=installed_client.env,
    )
    assert_success(generated, "generate the baseline project")
    # A local commit needs its own identity; a bare CI runner has no global one.
    _git("config", "user.name", "Test", cwd=dest)
    _git("config", "user.email", "test@example.com", cwd=dest)
    assert _git("status", "--porcelain", cwd=dest).strip() == ""
    return dest


@pytest.fixture
def scenario(
    installed_client: InstalledClient, baseline: Path, tmp_path: Path
) -> Scenario:
    project = tmp_path / "project"
    shutil.copytree(baseline, project, symlinks=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_bytes(SENTINEL)
    return Scenario(client=installed_client, project=project, outside=outside)


# --------------------------------------------------------------------------- #
# the candidate under test                                                    #
# --------------------------------------------------------------------------- #


def test_the_suite_runs_against_the_candidate_and_the_pinned_provider(
    installed_client: InstalledClient,
) -> None:
    """The evidence is only as good as what it is bound to: the console under
    test reports the client version this repository declares and exactly the
    provider the harness pinned. A release that bumps one and not the other
    fails here rather than being validated as something it is not.
    """
    version = run(
        [str(installed_client.console), "--version"],
        installed_client.root,
        env=installed_client.env,
    )
    doctor = run(
        [str(installed_client.console), "doctor", "--json"],
        installed_client.root,
        env=installed_client.env,
    )

    assert_success(version, "--version")
    assert version.stdout.strip() == CLIENT_VERSION
    # `doctor`'s exit status also reflects unrelated environment checks -- a bare
    # CI runner has no git identity, so it exits 1 there -- so only its JSON
    # report of the client and the provider matters here.
    report = json.loads(doctor.stdout)
    assert report["create_forge"] == CLIENT_VERSION
    assert report["integration"]["engine_package"] == ENGINE_VERSION


# --------------------------------------------------------------------------- #
# normal (engine-native) route                                                #
# --------------------------------------------------------------------------- #


def test_normal_route_no_op_update_changes_nothing(scenario: Scenario) -> None:
    """create-forge#214: rule 15's "byte-identical" is now an exact
    comparison, including `.forge/generation.json` -- `write_recorded` no
    longer goes through `Path.write_text`, so there is no line-ending
    translation left to tolerate.
    """
    before = _state(scenario.project)

    result = scenario.update()

    assert_success(result, "no-op engine-native update")
    assert "Nothing changed" in _text(result)
    assert _state(scenario.project) == before


def test_normal_route_update_preserves_a_committed_local_edit(
    scenario: Scenario,
) -> None:
    readme = scenario.project / "README.md"
    edited = readme.read_bytes() + b"\nlocal edit\n"
    readme.write_bytes(edited)
    _commit_all(scenario.project, "local edit")
    before = _state(scenario.project)

    result = scenario.update()

    assert_success(result, "engine-native update over a local edit")
    assert readme.read_bytes() == edited
    assert _state(scenario.project) == before


def test_normal_route_dry_run_writes_nothing(scenario: Scenario) -> None:
    before = _state(scenario.project)

    result = scenario.update("--dry-run")

    assert_success(result, "engine-native --dry-run")
    assert "Dry run complete" in _text(result)
    assert _state(scenario.project) == before


# --------------------------------------------------------------------------- #
# degraded route: a real, staged change                                       #
# --------------------------------------------------------------------------- #


def test_degraded_update_applies_a_real_changed_removed_and_added_target(
    scenario: Scenario,
) -> None:
    arranged = _arrange_pending_changes(scenario)
    project = scenario.project

    result = scenario.update("--degraded")

    assert_success(result, "degraded update with pending changes")
    assert "3 clean, 0 conflicted" in _text(result)
    assert (project / "README.md").read_bytes() == arranged.readme_original
    assert not (project / "obsolete.txt").exists()
    assert (project / arranged.added_target).read_bytes() == arranged.added_original
    # Everything the update did is staged by the real `git add -A`; nothing is not.
    assert _git("diff", "--name-only", cwd=project).strip() == ""
    staged = set(_git("diff", "--cached", "--name-only", cwd=project).split())
    assert {"README.md", "obsolete.txt", arranged.added_target, METADATA} <= staged
    refreshed = json.loads((project / METADATA).read_text(encoding="utf-8"))
    assert refreshed["reproduction"]["mode"] == "degraded"
    assert arranged.user_file.read_bytes() == USER_DATA
    scenario.assert_sentinel_untouched()


def test_degraded_dry_run_lists_every_target_and_writes_nothing(
    scenario: Scenario,
) -> None:
    arranged = _arrange_pending_changes(scenario)
    before = _state(scenario.project)

    result = scenario.update("--degraded", "--dry-run")

    assert_success(result, "degraded --dry-run with pending changes")
    text = _text(result)
    assert "Dry run complete" in text
    assert "changed clean README.md" in text
    assert "removed clean obsolete.txt" in text
    assert f"added clean {arranged.added_target}" in text
    assert _state(scenario.project) == before
    assert arranged.user_file.read_bytes() == USER_DATA
    scenario.assert_sentinel_untouched()


# --------------------------------------------------------------------------- #
# containment (CF-22.01)                                                      #
# --------------------------------------------------------------------------- #


def _tamper_with_the_sentinel(scenario: Scenario) -> State:
    """A recorded target that escapes the project, with the outside file's own
    digest -- the case that, before ADR 0052, was read and then deleted.
    """
    _doctor(scenario.project, _record_entry(_OUTSIDE_TARGET, _sha(SENTINEL)))
    _commit_all(scenario.project, "tamper with the recorded document")
    return _state(scenario.project)


@pytest.mark.parametrize("dry_run", [False, True], ids=["real", "dry-run"])
def test_degraded_update_refuses_a_recorded_target_outside_the_project(
    scenario: Scenario, dry_run: bool
) -> None:
    before = _tamper_with_the_sentinel(scenario)

    result = scenario.update("--degraded", *(["--dry-run"] if dry_run else []))

    assert result.returncode == 1, _text(result)
    text = _text(result)
    assert "unsafe update target" in text
    # Refused before anything changed, so there is nothing to recover -- and no
    # command that would discard a working tree is printed.
    assert "nothing to recover" in text
    assert "git restore" not in text
    assert _state(scenario.project) == before
    scenario.assert_sentinel_untouched()


def test_normal_route_refuses_a_tampered_recorded_document(
    scenario: Scenario,
) -> None:
    """The engine-native route refuses a tampered recorded document too, with
    nothing outside or inside changed. The entry is schema-valid on purpose, so
    the refusal is about its *target*, not about a malformed entry.
    """
    before = _tamper_with_the_sentinel(scenario)

    result = scenario.update()

    assert result.returncode == 1, _text(result)
    # Observed layer: the *provider* refuses it first, validating the recorded
    # document against the old render, so the client's own boundary is never
    # reached on this route -- it is defence in depth here, and is exercised
    # installed by the degraded route above.
    assert "invalid-generation-metadata" in _text(result)
    assert "nothing to recover" in _text(result)
    assert "git restore" not in _text(result)
    assert _state(scenario.project) == before
    scenario.assert_sentinel_untouched()


def test_a_recorded_git_hook_target_is_refused_and_left_alone(
    scenario: Scenario,
) -> None:
    hook = scenario.project / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_bytes(b"#!/bin/sh\nexit 0\n")
    _doctor(
        scenario.project,
        _record_entry(".git/hooks/pre-commit", _sha(hook.read_bytes())),
    )
    _commit_all(scenario.project, "record a hook")
    before = _state(scenario.project)

    result = scenario.update("--degraded")

    assert result.returncode == 1, _text(result)
    assert "excluded target" in _text(result)
    assert hook.read_bytes() == b"#!/bin/sh\nexit 0\n"
    assert _state(scenario.project) == before


def test_an_invalid_late_target_leaves_a_valid_changed_target_unwritten(
    scenario: Scenario,
) -> None:
    """Whole-update preflight, through the installed console: `README.md` is
    pristine per its recorded digest and would be replaced, but the bad target
    recorded beside it refuses the whole update before anything is written.
    """
    project = scenario.project
    readme = project / "README.md"
    edited = readme.read_bytes() + b"\nlocal edit\n"
    readme.write_bytes(edited)
    _doctor(project, _record_digest("README.md", _sha(edited)))
    _doctor(project, _record_entry(_OUTSIDE_TARGET, _sha(SENTINEL)))
    _commit_all(project, "a valid changed target and a bad one")
    before = _state(project)

    result = scenario.update("--degraded")

    assert result.returncode == 1, _text(result)
    assert readme.read_bytes() == edited
    assert _state(project) == before
    scenario.assert_sentinel_untouched()


@pytest.mark.skipif(os.name == "nt", reason="symlinked-parent case is POSIX-only")
def test_a_symlinked_parent_that_escapes_is_refused(scenario: Scenario) -> None:
    project = scenario.project
    top = next(
        target.split("/")[0]
        for target in _recorded_targets(project)
        if "/" in target and not target.startswith(".")
    )
    moved = scenario.outside / top
    shutil.move(str(project / top), str(moved))
    (project / top).symlink_to(moved, target_is_directory=True)
    _commit_all(project, f"replace {top}/ with a link that leaves the project")
    before = _state(project)
    outside_before = file_bytes(scenario.outside)

    result = scenario.update("--degraded")

    assert result.returncode == 1, _text(result)
    assert "resolves outside the project" in _text(result)
    assert _state(project) == before
    assert file_bytes(scenario.outside) == outside_before


# --------------------------------------------------------------------------- #
# recovery (CF-22.02)                                                         #
# --------------------------------------------------------------------------- #


def test_the_documented_recovery_restores_a_completed_staged_update(
    scenario: Scenario,
) -> None:
    """What a user does to abandon a finished update: the documented commands,
    from the repository root, restoring the committed baseline and leaving a
    file they own (and Git ignores) alone.
    """
    arranged = _arrange_pending_changes(scenario)
    assert_success(scenario.update("--degraded"), "the update to abandon")
    assert _git("status", "--porcelain", cwd=scenario.project).strip() != ""

    _git(*RESTORE_ARGV[1:], cwd=scenario.project)
    untracked = _git(*CLEAN_PREVIEW_ARGV[1:], cwd=scenario.project)
    _git(*CLEAN_ARGV[1:], cwd=scenario.project)

    assert "__pycache__" not in untracked  # ignored files are never candidates
    assert _state(scenario.project) == arranged.baseline
    assert arranged.user_file.read_bytes() == USER_DATA


def test_an_interrupted_update_prints_guidance_that_recovers_it(
    scenario: Scenario,
) -> None:
    """A real interruption: `.git/index.lock` makes the real `git add -A` fail
    after every file was written. The guidance the installed console *prints* is
    then pasted verbatim, from a directory outside the repository, and must
    return the project to the committed baseline.
    """
    arranged = _arrange_pending_changes(scenario)
    lock = scenario.project / ".git" / "index.lock"
    lock.write_bytes(b"")

    result = scenario.update("--degraded")

    assert result.returncode == 1, _text(result)
    assert "Nothing changed" not in _text(result)
    lock.unlink()  # the interruption is over; the lock would not outlive it
    commands = [
        line.strip() for line in result.stderr.splitlines() if line.startswith("  git ")
    ]
    assert len(commands) == 3, result.stderr  # restore, preview, delete
    assert "restore --source=HEAD --staged --worktree ." in commands[0]
    assert commands[1].endswith("-nd")
    assert commands[2].endswith("-fd")
    assert str(scenario.project) in commands[0]  # anchored at the repository root

    for index, command in enumerate(commands):
        completed = subprocess.run(  # noqa: S602 - the printed line, as a user pastes it
            command,
            shell=True,
            cwd=scenario.outside,
            check=True,
            capture_output=True,
            timeout=60,
        )
        if index == 1:
            listing = completed.stdout.decode("utf-8", errors="replace")
            assert arranged.added_target in listing
            assert "__pycache__" not in listing

    assert _state(scenario.project) == arranged.baseline
    assert arranged.user_file.read_bytes() == USER_DATA
    scenario.assert_sentinel_untouched()


def test_a_dirty_tree_is_refused_without_offering_to_discard_it(
    scenario: Scenario,
) -> None:
    """Published 0.4.0 printed a recovery command here that would have thrown
    away the user's own uncommitted work. The update never started, so nothing
    is offered for discard.
    """
    project = scenario.project
    notes = project / "my-notes.txt"
    notes.write_bytes(b"work in progress\n")
    readme = project / "README.md"
    mine = readme.read_bytes() + b"\nmy own edit\n"
    readme.write_bytes(mine)
    before = _state(project)

    result = scenario.update()

    assert result.returncode == 1, _text(result)
    text = _text(result)
    assert "uncommitted changes" in text
    for fragment in ("git restore", "git clean", "nothing to recover", "git -C"):
        assert fragment not in text
    assert notes.read_bytes() == b"work in progress\n"
    assert readme.read_bytes() == mine
    assert _state(project) == before
