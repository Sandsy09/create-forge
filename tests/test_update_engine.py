"""Engine-native `update` application (CF-18.04, ADR 0041 rules 9-23, ADR
0046): the Git working-tree precondition, per-target application of a
provider-shaped `UpdatePlan`, the real `git merge-file` three-way merge, and
the client-owned degraded fallback.

Real `git`, no network in the fast suite: every fast test below builds an
actual repository under `tmp_path` -- the same "dogfood the real tool" choice
`tests/test_update.py` makes for Copier, and the only way to prove
`git merge-file`'s own conflict-marker behaviour rather than assuming it.
`-k dry_run`/`-k recover`/`-k degraded` name the acceptance-matrix's own
evidence commands (`docs/engine-cutover-acceptance.md`). Most of this module
tests `create_forge.update`'s own logic with fake `UpdateTargetView`/
`AppliedRenameView` values -- no `forge_template` import needed there at all.
The `pipeline.prepare_update` short-circuit test is the one fast-suite place
a real (but required, always-installed) engine render is used, to prove the
orchestration seam without needing a second engine version to update from.

The `@pytest.mark.e2e` tests at the end need network: one runs the real
console script end to end (`new` then `update`), the other provisions the
`../forge-template` sibling checkout as a stand-in recorded release to
exercise `pipeline._reproduce_old`'s provisioning branch for real -- no
forge-template release before `0.5.0` ever writes generation metadata, so a
genuinely older recorded release does not exist to test against (ADR 0046).
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from create_forge import engine, engine_source, pipeline
from create_forge.spec import SelectionRequest, build_spec_payload
from create_forge.update import (
    RESTORE_COMMAND,
    UpdateError,
    apply_plan,
    apply_renames,
    degraded_plan,
    merge_target,
    read_recorded,
    relock,
    require_clean_tree,
    stage_result,
)
from tests.process import run_text

METADATA_FILE = ".forge/generation.json"


def _git(*args: str, cwd: Path) -> str:
    return run_text(["git", *args], cwd=cwd, check=True, timeout=30).stdout


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "--quiet", "--initial-branch=main", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "core.autocrlf", "false", cwd=path)


def _commit(path: Path, message: str = "commit") -> None:
    _git("add", "-A", cwd=path)
    _git("commit", "--quiet", "-m", message, cwd=path)


@dataclass(frozen=True, slots=True)
class _Target:
    """A fake `forge_template.UpdateTarget` -- structurally sufficient for
    `update.UpdateTargetView`, with no engine import.
    """

    target: str
    classification: str
    regeneration: str = "replace"


@dataclass(frozen=True, slots=True)
class _Rename:
    """A fake `forge_template.AppliedRename`."""

    component_id: str
    from_: str
    to: str
    since: str = "1.1.0"


# --------------------------------------------------------------------------- #
# require_clean_tree                                                          #
# --------------------------------------------------------------------------- #


def test_require_clean_tree_rejects_a_non_git_directory(tmp_path: Path) -> None:
    with pytest.raises(UpdateError, match="not a Git repository"):
        require_clean_tree(tmp_path)


def test_require_clean_tree_rejects_a_dirty_tree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    _commit(tmp_path)
    (tmp_path / "a.txt").write_text("b", encoding="utf-8")

    with pytest.raises(UpdateError, match="uncommitted changes"):
        require_clean_tree(tmp_path)


def test_require_clean_tree_accepts_a_clean_tree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    _commit(tmp_path)

    require_clean_tree(tmp_path)  # must not raise


# --------------------------------------------------------------------------- #
# apply_renames                                                               #
# --------------------------------------------------------------------------- #


def test_apply_renames_moves_the_working_tree_file(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "old.txt").write_text("content", encoding="utf-8")
    _commit(tmp_path)

    apply_renames(
        tmp_path, [_Rename(component_id="widget", from_="old.txt", to="new.txt")]
    )

    assert not (tmp_path / "old.txt").exists()
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"


def test_apply_renames_skips_an_already_moved_source(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "new.txt").write_text("content", encoding="utf-8")
    _commit(tmp_path)

    apply_renames(
        tmp_path, [_Rename(component_id="widget", from_="old.txt", to="new.txt")]
    )  # must not raise -- old.txt never existed

    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"


# --------------------------------------------------------------------------- #
# merge_target -- the real git merge-file three-way merge                     #
# --------------------------------------------------------------------------- #


def test_merge_target_merges_non_overlapping_changes_cleanly() -> None:
    base = b"line1\nline2\nline3\n"
    ours = b"line1 (local edit)\nline2\nline3\n"
    theirs = b"line1\nline2\nline3 (template edit)\n"

    merged, conflicted = merge_target(base=base, ours=ours, theirs=theirs)

    assert not conflicted
    assert merged == b"line1 (local edit)\nline2\nline3 (template edit)\n"


def test_merge_target_reports_a_genuine_conflict() -> None:
    base = b"line1\n"
    ours = b"local version\n"
    theirs = b"template version\n"

    merged, conflicted = merge_target(base=base, ours=ours, theirs=theirs)

    assert conflicted
    assert b"<<<<<<<" in merged
    assert b"local version" in merged
    assert b"template version" in merged
    assert b"=======" in merged
    assert b">>>>>>>" in merged


# --------------------------------------------------------------------------- #
# apply_plan -- every classification                                         #
# --------------------------------------------------------------------------- #


def test_apply_plan_writes_a_new_added_target(tmp_path: Path) -> None:
    outcome = apply_plan(
        tmp_path,
        [_Target(target="new.txt", classification="added")],
        [],
        old={},
        new={"new.txt": b"content"},
        dry_run=False,
    )

    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "content"
    assert outcome.results[0].status == "clean"


def test_apply_plan_replaces_a_pristine_changed_target(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_bytes(b"old content")

    outcome = apply_plan(
        tmp_path,
        [_Target(target="f.txt", classification="changed")],
        [],
        old={"f.txt": b"old content"},
        new={"f.txt": b"new content"},
        dry_run=False,
    )

    assert (tmp_path / "f.txt").read_bytes() == b"new content"
    assert outcome.results[0].status == "clean"


def test_apply_plan_merges_a_locally_edited_changed_target(tmp_path: Path) -> None:
    # An unchanged middle line gives `git merge-file` the context it needs to
    # tell the two edits apart -- with none, even non-overlapping edits to a
    # two-line file conflict (verified directly against real `git merge-file`).
    (tmp_path / "f.txt").write_bytes(b"line1 (local)\nline2\nline3\n")

    outcome = apply_plan(
        tmp_path,
        [_Target(target="f.txt", classification="changed")],
        [],
        old={"f.txt": b"line1\nline2\nline3\n"},
        new={"f.txt": b"line1\nline2\nline3 (template)\n"},
        dry_run=False,
    )

    expected = b"line1 (local)\nline2\nline3 (template)\n"
    assert (tmp_path / "f.txt").read_bytes() == expected
    assert outcome.results[0].status == "clean"


def test_apply_plan_leaves_a_binary_conflict_untouched(tmp_path: Path) -> None:
    (tmp_path / "f.bin").write_bytes(b"\x00\x01local")

    outcome = apply_plan(
        tmp_path,
        [_Target(target="f.bin", classification="changed")],
        [],
        old={"f.bin": b"\x00\x01old"},
        new={"f.bin": b"\x00\x01new"},
        dry_run=False,
    )

    assert (tmp_path / "f.bin").read_bytes() == b"\x00\x01local"
    assert outcome.results[0].status == "conflict"


def test_apply_plan_respects_a_local_deletion_of_a_changed_target(
    tmp_path: Path,
) -> None:
    outcome = apply_plan(
        tmp_path,
        [_Target(target="gone.txt", classification="changed")],
        [],
        old={"gone.txt": b"old"},
        new={"gone.txt": b"new"},
        dry_run=False,
    )

    assert not (tmp_path / "gone.txt").exists()
    assert outcome.results[0].status == "skipped"


def test_apply_plan_deletes_a_pristine_removed_target(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_bytes(b"old content")

    outcome = apply_plan(
        tmp_path,
        [_Target(target="old.txt", classification="removed")],
        [],
        old={"old.txt": b"old content"},
        new={},
        dry_run=False,
    )

    assert not (tmp_path / "old.txt").exists()
    assert outcome.results[0].status == "clean"


def test_apply_plan_keeps_a_locally_modified_removed_target(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_bytes(b"locally modified")

    outcome = apply_plan(
        tmp_path,
        [_Target(target="old.txt", classification="removed")],
        [],
        old={"old.txt": b"old content"},
        new={},
        dry_run=False,
    )

    assert (tmp_path / "old.txt").read_bytes() == b"locally modified"
    assert outcome.results[0].status == "conflict"


def test_apply_plan_never_touches_a_skip_if_exists_target(tmp_path: Path) -> None:
    (tmp_path / "CHANGELOG.md").write_bytes(b"user content")

    outcome = apply_plan(
        tmp_path,
        [
            _Target(
                target="CHANGELOG.md",
                classification="changed",
                regeneration="skip-if-exists",
            )
        ],
        [],
        old={"CHANGELOG.md": b"old"},
        new={"CHANGELOG.md": b"new"},
        dry_run=False,
    )

    assert (tmp_path / "CHANGELOG.md").read_bytes() == b"user content"
    assert outcome.results[0].status == "skipped"


def test_apply_plan_reports_unchanged_without_touching_disk(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_bytes(b"same")

    outcome = apply_plan(
        tmp_path,
        [_Target(target="f.txt", classification="unchanged")],
        [],
        old={"f.txt": b"same"},
        new={"f.txt": b"same"},
        dry_run=False,
    )

    assert outcome.results[0].status == "unchanged"
    assert outcome.changed == 0


def test_apply_plan_uses_the_pre_rename_path_for_old_bytes(tmp_path: Path) -> None:
    """A `renamed` target's *old* content is keyed by its pre-move path, not
    its new one -- `apply_renames` already moved the working-tree file there.

    Uses non-overlapping single-line edits so the three-way merge resolves
    cleanly regardless of merge order, isolating the assertion to "the right
    base was used" rather than merge mechanics `merge_target`'s own tests
    already cover.
    """
    (tmp_path / "new_name.txt").write_bytes(b"line1 (local)\nline2\nline3\n")

    outcome = apply_plan(
        tmp_path,
        [_Target(target="new_name.txt", classification="renamed")],
        [_Rename(component_id="widget", from_="old_name.txt", to="new_name.txt")],
        old={"old_name.txt": b"line1\nline2\nline3\n"},
        new={"new_name.txt": b"line1\nline2\nline3 (template)\n"},
        dry_run=False,
    )

    expected = b"line1 (local)\nline2\nline3 (template)\n"
    assert (tmp_path / "new_name.txt").read_bytes() == expected
    assert outcome.results[0].status == "clean"


def test_apply_plan_dry_run_writes_nothing(tmp_path: Path) -> None:
    outcome = apply_plan(
        tmp_path,
        [
            _Target(target="new.txt", classification="added"),
            _Target(target="old.txt", classification="removed"),
        ],
        [],
        old={"old.txt": b"content"},
        new={"new.txt": b"content"},
        dry_run=True,
    )

    assert not (tmp_path / "new.txt").exists()
    assert outcome.results[0].status == "clean"


def test_apply_plan_sorts_results_by_target(tmp_path: Path) -> None:
    outcome = apply_plan(
        tmp_path,
        [
            _Target(target="z.txt", classification="added"),
            _Target(target="a.txt", classification="added"),
        ],
        [],
        old={},
        new={"z.txt": b"z", "a.txt": b"a"},
        dry_run=False,
    )

    assert [r.target for r in outcome.results] == ["a.txt", "z.txt"]


# --------------------------------------------------------------------------- #
# degraded_plan -- the client-owned, no-merge-base fallback                   #
# --------------------------------------------------------------------------- #


def test_degraded_plan_replaces_a_pristine_target(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_bytes(b"old content")
    digest = "sha256:" + hashlib.sha256(b"old content").hexdigest()

    outcome = degraded_plan(
        tmp_path,
        {"f.txt": b"new content"},
        recorded_digests={"f.txt": digest},
        dry_run=False,
    )

    assert (tmp_path / "f.txt").read_bytes() == b"new content"
    assert outcome.results[0].status == "clean"


def test_degraded_plan_leaves_a_locally_modified_target_alone(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_bytes(b"locally modified")
    stale_digest = "sha256:" + "0" * 64

    outcome = degraded_plan(
        tmp_path,
        {"f.txt": b"new content"},
        recorded_digests={"f.txt": stale_digest},
        dry_run=False,
    )

    assert (tmp_path / "f.txt").read_bytes() == b"locally modified"
    assert outcome.results[0].status == "conflict"


def test_degraded_plan_adds_a_new_target(tmp_path: Path) -> None:
    outcome = degraded_plan(
        tmp_path, {"new.txt": b"content"}, recorded_digests={}, dry_run=False
    )

    assert (tmp_path / "new.txt").read_bytes() == b"content"
    assert outcome.results[0].status == "clean"


def test_degraded_plan_deletes_a_pristine_removed_target(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_bytes(b"old content")
    digest = "sha256:" + hashlib.sha256(b"old content").hexdigest()

    outcome = degraded_plan(
        tmp_path, {}, recorded_digests={"old.txt": digest}, dry_run=False
    )

    assert not (tmp_path / "old.txt").exists()
    assert outcome.results[0].status == "clean"


def test_degraded_plan_keeps_a_locally_modified_removed_target(tmp_path: Path) -> None:
    (tmp_path / "old.txt").write_bytes(b"locally modified")
    stale_digest = "sha256:" + "0" * 64

    outcome = degraded_plan(
        tmp_path, {}, recorded_digests={"old.txt": stale_digest}, dry_run=False
    )

    assert (tmp_path / "old.txt").read_bytes() == b"locally modified"
    assert outcome.results[0].status == "conflict"


def test_degraded_plan_dry_run_writes_nothing(tmp_path: Path) -> None:
    outcome = degraded_plan(
        tmp_path, {"new.txt": b"content"}, recorded_digests={}, dry_run=True
    )

    assert not (tmp_path / "new.txt").exists()
    assert outcome.results[0].status == "clean"


# --------------------------------------------------------------------------- #
# stage_result / relock                                                       #
# --------------------------------------------------------------------------- #


def test_stage_result_stages_new_files(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    _commit(tmp_path)
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    stage_result(tmp_path)

    status = _git("status", "--porcelain", cwd=tmp_path)
    assert status.strip() == "A  b.txt"


def test_relock_warns_and_does_not_raise_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    warning = relock(tmp_path)

    assert warning is not None
    assert "uv lock failed" in warning


# --------------------------------------------------------------------------- #
# pipeline.prepare_update -- the version-match short-circuit (real engine)    #
# --------------------------------------------------------------------------- #


def _write_recorded_document(project: Path, spec_payload: dict[str, object]) -> None:
    """Record a *real* render's own metadata document -- not a hand-built
    one: `plan_update` digest-verifies `old` against every recorded `output`
    entry, so the recorded document must actually match what this spec
    renders to on the installed engine, exactly as a real `new` would commit.
    """
    validated = engine.validate(engine.build_project_spec(spec_payload))
    rendered = engine.render(validated)
    metadata = rendered.metadata
    if metadata is None:  # pragma: no cover - contractually always populated
        raise AssertionError("the engine returned no generation metadata")
    metadata_path = project / METADATA_FILE
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(metadata.to_json(), encoding="utf-8")


def test_prepare_update_short_circuits_on_a_matching_version(tmp_path: Path) -> None:
    """A recorded provider version equal to the installed one never provisions
    anything (decision 1) -- every target classifies `unchanged` since the
    effective spec is the recorded spec verbatim (decision 5), the classic
    no-op/repeated-update case (ADR 0041 rule 15).
    """
    answers = {
        "project_name": "Update Smoke",
        "license": "mit",
        "author_name": "Test",
        "author_email": "test@example.invalid",
    }
    selection = SelectionRequest.of(archetype="library")
    spec_payload = build_spec_payload(
        answers, archetype=selection.archetype, capabilities=(), platforms=()
    )
    _write_recorded_document(tmp_path, spec_payload)

    preparation = pipeline.prepare_update(tmp_path)

    assert all(
        target.classification == "unchanged" for target in preparation.plan.targets
    )
    assert preparation.old == {f.target: f.content for f in preparation.new.files}


# --------------------------------------------------------------------------- #
# Recovery: why the restore must cover the index (CF-22.02, ADR 0053)         #
# --------------------------------------------------------------------------- #
#
# The recovery guidance itself -- every state an update can leave behind, the
# printed commands actually executed, the CLI wiring -- is
# tests/test_update_recovery.py's job. This only pins the premise ADR 0041's
# rule 18 got wrong, next to the functions that break it.


def test_recovery_restores_the_index_because_an_update_stages_its_result(
    tmp_path: Path,
) -> None:
    """Rule 18 assumed "a failure mid-update never leaves anything staged".

    `stage_result` runs `git add -A`, so a completed update *is* staged, and
    `git restore .` -- which restores the worktree from the index -- undoes
    none of it. `RESTORE_COMMAND` names `HEAD` as the source and restores both.
    """
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("original a\n", encoding="utf-8")
    _commit(tmp_path)
    (tmp_path / "a.txt").write_text("merged a\n", encoding="utf-8")
    stage_result(tmp_path)

    assert _git("diff", "--cached", "--name-only", cwd=tmp_path).split() == ["a.txt"]

    _git("restore", ".", cwd=tmp_path)  # what published 0.4.0 printed
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "merged a\n"

    _git(*RESTORE_COMMAND[1:], cwd=tmp_path)
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "original a\n"
    assert _git("status", "--porcelain", cwd=tmp_path).strip() == ""


def test_apply_renames_stages_the_move_so_an_interrupted_rename_is_not_unstaged(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "old.txt").write_text("content\n", encoding="utf-8")
    _commit(tmp_path)

    apply_renames(tmp_path, [_Rename("c", "old.txt", "new.txt")])

    assert _git("status", "--porcelain", cwd=tmp_path).split()[0] == "R"


def test_read_recorded_is_reused_by_pipeline() -> None:
    """`pipeline.prepare_update`/`prepare_degraded_update` both call
    `update.read_recorded` rather than re-implementing the parse -- a smoke
    check that the import path stays intact.
    """
    assert read_recorded.__module__ == "create_forge.update"


# --------------------------------------------------------------------------- #
# Real console-script and provisioning-path e2e (network-heavy)              #
# --------------------------------------------------------------------------- #

_SIBLING_FORGE_TEMPLATE = (
    Path(__file__).resolve().parent.parent.parent / "forge-template"
)


@pytest.mark.e2e
def test_real_console_update_on_a_freshly_generated_project(
    tmp_path: Path, create_forge_command: str, e2e_child_env: dict[str, str]
) -> None:
    """A full round trip through the real console script: `new` then
    `update`. With only one `forge-template` release installed this is
    always a no-op (old == new) -- decision 2's short-circuit -- but it
    proves `create-forge update` works end to end against a real generated
    project: real git, the real engine, a real CLI process, not the fast
    suite's fakes.
    """
    project = tmp_path / "update-smoke"
    new_result = run_text(
        [
            create_forge_command,
            "new",
            "Update Smoke",
            "--yes",
            "--archetype",
            "library",
            "--no-capabilities",
            "--no-platforms",
            "--data",
            "project_description=create-forge update e2e smoke test.",
            "--data",
            "license=mit",
            "--data",
            "author_name=create-forge e2e",
            "--data",
            "author_email=create-forge-e2e@example.invalid",
            "--path",
            str(project),
        ],
        timeout=300,
        check=False,
        env=e2e_child_env,
    )
    assert new_result.returncode == 0, new_result.stdout + new_result.stderr

    update_result = run_text(
        [create_forge_command, "update", str(project)],
        timeout=300,
        check=False,
        env=e2e_child_env,
    )
    assert update_result.returncode == 0, update_result.stdout + update_result.stderr
    assert "Nothing changed." in update_result.stdout

    status = _git("status", "--porcelain", cwd=project)
    assert status.strip() == ""


@pytest.mark.e2e
@pytest.mark.skipif(
    not _SIBLING_FORGE_TEMPLATE.is_dir(),
    reason="no sibling ../forge-template checkout to provision",
)
def test_prepare_update_provisions_the_recorded_release_when_versions_differ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decision 2's provisioning branch, exercised for real.

    The `../forge-template` sibling checkout stands in for "the recorded
    release" -- its shipped engine modules are byte-identical to the
    installed `0.5.0` wheel, so rendering the same spec through it produces
    the same bytes `plan_update`'s digest check requires, even though its
    `provider.version` string differs from what is actually installed.
    `engine_source.released_requirement` is redirected to the local checkout
    path instead of a PyPI `==` pin -- the one seam a real historical release
    would use unmodified.
    """
    answers = {
        "project_name": "Update Provision Smoke",
        "license": "mit",
        "author_name": "Test",
        "author_email": "test@example.invalid",
    }
    selection = SelectionRequest.of(archetype="library")
    spec_payload = build_spec_payload(
        answers, archetype=selection.archetype, capabilities=(), platforms=()
    )
    new = engine.render(engine.validate(engine.build_project_spec(spec_payload)))
    if new.metadata is None:  # pragma: no cover - contractually always populated
        raise AssertionError("the engine returned no generation metadata")

    # A recorded provider.version that does not match the installed one --
    # forcing pipeline._reproduce_old past the short-circuit -- while every
    # other field (spec, output digests) matches the real render above.
    recorded = new.metadata.model_copy(
        update={
            "provider": new.metadata.provider.model_copy(
                update={"version": "0.0.0-sibling-checkout"}
            )
        }
    )
    metadata_path = tmp_path / METADATA_FILE
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(recorded.to_json(), encoding="utf-8")

    def _sibling_requirement(_version: str) -> str:
        return str(_SIBLING_FORGE_TEMPLATE)

    monkeypatch.setattr(engine_source, "released_requirement", _sibling_requirement)

    preparation = pipeline.prepare_update(tmp_path)

    assert all(
        target.classification == "unchanged" for target in preparation.plan.targets
    )
