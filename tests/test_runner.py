"""`runner.scaffold`'s staging integration (ADR 0015): a non-empty destination
is rejected before Copier ever runs, and a `run_copy` failure removes a
destination `create-forge` created but leaves a pre-existing one untouched.

`run_copy` itself is monkeypatched to raise -- Copier's own rendering
behaviour is exercised for real by `tests/test_update.py` and
`tests/test_cli.py`; this file isolates the staging/cleanup integration
`runner.scaffold` now wraps around it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from copier.errors import CopierError
from plumbum.commands.processes import ProcessExecutionError

import create_forge.runner as runner_module
from create_forge.runner import ScaffoldError, ScaffoldRequest, scaffold, update


def _request(dst: Path) -> ScaffoldRequest:
    return ScaffoldRequest(src="does-not-matter", dst=dst, data={})


def test_scaffold_rejects_a_non_empty_destination_before_calling_copier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "proj"
    dst.mkdir()
    (dst / "existing.txt").write_text("hi", encoding="utf-8")

    def unexpected_run_copy(**_kwargs: object) -> None:
        raise AssertionError("run_copy must not run against a non-empty destination")

    monkeypatch.setattr(runner_module, "run_copy", unexpected_run_copy)

    with pytest.raises(ScaffoldError, match="already exists and is not empty"):
        scaffold(_request(dst))


def test_scaffold_removes_a_destination_it_created_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "proj"

    def failing_run_copy(**kwargs: object) -> None:
        # A realistic partial Copier run: some output landed before the
        # failure.
        Path(str(kwargs["dst_path"])).mkdir(parents=True, exist_ok=True)
        (Path(str(kwargs["dst_path"])) / "partial.txt").write_text(
            "x", encoding="utf-8"
        )
        raise CopierError("simulated render failure")

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)

    with pytest.raises(ScaffoldError):
        scaffold(_request(dst))

    assert not dst.exists()


def test_scaffold_leaves_a_pre_existing_destination_untouched_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "proj"
    dst.mkdir()  # exists and is empty -- a legitimate --path target

    def failing_run_copy(**_kwargs: object) -> None:
        raise CopierError("simulated render failure")

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)

    with pytest.raises(ScaffoldError):
        scaffold(_request(dst))

    assert dst.is_dir()


def test_scaffold_leaves_the_destination_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "proj"

    def succeeding_run_copy(**kwargs: object) -> None:
        Path(str(kwargs["dst_path"])).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(runner_module, "run_copy", succeeding_run_copy)

    scaffold(_request(dst))

    assert dst.is_dir()


def test_scaffold_explains_a_real_missing_template_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = tmp_path / "copier-settings.yml"
    settings.write_text("{}\n", encoding="utf-8")
    monkeypatch.setenv("COPIER_SETTINGS_PATH", str(settings))
    monkeypatch.setenv("COPIER_CACHE_DIR", str(tmp_path / "copier-cache"))
    missing_source = tmp_path / "missing-template.git"
    dst = tmp_path / "proj"
    request = ScaffoldRequest(src=str(missing_source), dst=dst, data={}, vcs_ref="HEAD")

    with pytest.raises(
        ScaffoldError, match="Git could not complete the template operation"
    ) as raised:
        scaffold(request)

    assert isinstance(raised.value.__cause__, ProcessExecutionError)
    assert str(missing_source) not in str(raised.value)
    assert "Unexpected exit code" not in str(raised.value)
    assert not dst.exists()


def test_scaffold_explains_an_unusable_copier_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0039: a git failure that reports a missing repository *at the
    resolved cache path* gets COPIER_CACHE_DIR recovery guidance -- and still
    none of the process output that revealed it.
    """
    cache_dir = tmp_path / "corp cache"
    monkeypatch.setenv("COPIER_CACHE_DIR", str(cache_dir))
    mirror = cache_dir / "deadbeef.git"
    process_error = ProcessExecutionError(
        ["git", "--git-dir", str(mirror), "rev-parse", "--is-bare-repository"],
        128,
        "",
        f"fatal: not a git repository: '{mirror}'",
    )

    def failing_run_copy(**kwargs: object) -> None:
        partial = Path(str(kwargs["dst_path"]))
        partial.mkdir(parents=True)
        (partial / "partial.txt").write_text("x", encoding="utf-8")
        raise process_error

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)
    dst = tmp_path / "proj"

    with pytest.raises(ScaffoldError) as raised:
        scaffold(ScaffoldRequest(src="https://example.invalid/t.git", dst=dst, data={}))

    message = str(raised.value)
    assert "COPIER_CACHE_DIR" in message
    assert str(cache_dir) in message  # our own resolved path is fine to show
    for hidden in ("not a git repository", "rev-parse", "--git-dir", "deadbeef.git"):
        assert hidden not in message
    assert raised.value.__cause__ is process_error
    assert not dst.exists()


def test_scaffold_auth_failure_near_the_cache_keeps_generic_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC 4: an auth failure whose mirror-clone target happens to sit under
    the cache directory is not the cache condition -- it keeps the existing
    generic message, because the "not a git repository" signal is absent.
    """
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("COPIER_CACHE_DIR", str(cache_dir))
    mirror = cache_dir / "deadbeef.git"
    process_error = ProcessExecutionError(
        ["git", "clone", "--mirror", "https://example.invalid/t.git", str(mirror)],
        128,
        "",
        "fatal: Authentication failed for 'https://example.invalid/t.git'",
    )

    def failing_run_copy(**kwargs: object) -> None:
        Path(str(kwargs["dst_path"])).mkdir(parents=True)
        raise process_error

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)
    dst = tmp_path / "proj"

    with pytest.raises(ScaffoldError, match="Git could not complete") as raised:
        scaffold(ScaffoldRequest(src="https://example.invalid/t.git", dst=dst, data={}))

    assert "COPIER_CACHE_DIR" not in str(raised.value)


def test_scaffold_explains_an_os_error_at_the_cache_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0039: an unwritable cache fails inside Copier as a bare OSError
    from `mirror.parent.mkdir`, not through git. `runner` still classifies it
    when the failing path is the resolved cache directory.
    """
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("COPIER_CACHE_DIR", str(cache_dir))

    def failing_run_copy(**kwargs: object) -> None:
        Path(str(kwargs["dst_path"])).mkdir(parents=True)
        raise PermissionError(13, "Permission denied", str(cache_dir / "deadbeef.git"))

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)
    dst = tmp_path / "proj"

    with pytest.raises(ScaffoldError, match="COPIER_CACHE_DIR"):
        scaffold(_request(dst))

    assert not dst.exists()


def test_scaffold_propagates_an_os_error_outside_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The narrow-catch guarantee: an OSError whose path is not under the
    cache directory is re-raised untouched, never disguised as a ScaffoldError
    -- but the partial destination is still cleaned up.
    """
    monkeypatch.setenv("COPIER_CACHE_DIR", str(tmp_path / "cache"))

    def failing_run_copy(**kwargs: object) -> None:
        Path(str(kwargs["dst_path"])).mkdir(parents=True)
        raise PermissionError(
            13, "Permission denied", str(tmp_path / "elsewhere" / "x")
        )

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)
    dst = tmp_path / "proj"

    with pytest.raises(PermissionError):
        scaffold(_request(dst))

    assert not dst.exists()


def test_scaffold_classifies_a_cache_failure_named_only_in_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The signal can arrive without the path in the same string: a bare
    `fatal: not a git repository` in stderr, with the cache path only in argv,
    is still the cache condition.
    """
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("COPIER_CACHE_DIR", str(cache_dir))
    process_error = ProcessExecutionError(
        ["git", "--git-dir", str(cache_dir / "deadbeef.git"), "worktree", "prune"],
        128,
        "",
        "fatal: not a git repository (or any parent up to mount point)",
    )

    def failing_run_copy(**_kwargs: object) -> None:
        raise process_error

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)

    with pytest.raises(ScaffoldError, match="COPIER_CACHE_DIR"):
        scaffold(_request(tmp_path / "proj"))


def test_update_explains_an_unusable_copier_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `update` path grows the same narrow OSError catch as `scaffold`."""
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("COPIER_CACHE_DIR", str(cache_dir))
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".copier-answers.yml").write_text(
        f"_src_path: {tmp_path / 'template'}\n_commit: v1.0.0\n", encoding="utf-8"
    )

    def failing_run_update(**_kwargs: object) -> None:
        raise PermissionError(13, "Permission denied", str(cache_dir / "abc.git"))

    monkeypatch.setattr(runner_module, "run_update", failing_run_update)

    with pytest.raises(ScaffoldError, match="COPIER_CACHE_DIR"):
        update(project)


def test_scaffold_process_failure_hides_credentials_and_process_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "proj"
    sensitive = "do-not-display"
    source = "https://example.invalid/template.git"
    process_error = ProcessExecutionError(
        [
            "git",
            "clone",
            f"https://user:{sensitive}@example.invalid/template.git",
            "v1-secret-ref",
        ],
        128,
        f"sensitive stdout: {sensitive}",
        f"sensitive stderr: {sensitive}",
    )

    def failing_run_copy(**kwargs: object) -> None:
        partial = Path(str(kwargs["dst_path"]))
        partial.mkdir(parents=True)
        (partial / "partial.txt").write_text("x", encoding="utf-8")
        raise process_error

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)

    with pytest.raises(ScaffoldError) as raised:
        scaffold(ScaffoldRequest(src=source, dst=dst, data={}, vcs_ref="v1-secret-ref"))

    message = str(raised.value)
    assert message == (
        "Git could not complete the template operation.\n"
        "  Check the template URL and --ref, your network connection, repository "
        "access, and Git credentials, then retry."
    )
    assert raised.value.__cause__ is process_error
    for hidden in (
        sensitive,
        source,
        "v1-secret-ref",
        "sensitive stdout",
        "sensitive stderr",
        "git clone",
    ):
        assert hidden not in message
    assert not dst.exists()
