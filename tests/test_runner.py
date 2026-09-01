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
from create_forge.runner import ScaffoldError, ScaffoldRequest, scaffold


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


def test_scaffold_process_failure_hides_credentials_and_process_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dst = tmp_path / "proj"
    sensitive = "do-not-display"
    source = f"https://user:{sensitive}@example.invalid/template.git"
    process_error = ProcessExecutionError(
        ["git", "clone", source, "v1-secret-ref"],
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
