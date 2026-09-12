"""Credential sentinels must never cross the source/output boundary (#139)."""

from __future__ import annotations

import subprocess
import traceback
from pathlib import Path
from urllib.parse import quote

import pytest
import typer
import yaml
from copier.errors import CopierError
from plumbum.commands.processes import ProcessExecutionError
from rich.console import Console
from typer.testing import CliRunner

from create_forge import cli, runner, staging
from create_forge.config import UserConfig
from create_forge.sources import SourceError, display_source, validate_source

SECRET = "sentinel-credential!"  # noqa: S105 -- deliberately public test sentinel
ENCODED = quote(SECRET, safe="")
UNSAFE = [
    f"{scheme}://{userinfo}@example.invalid/template.git"
    for scheme in ("http", "https", "git+https")
    for userinfo in (SECRET, f"user:{SECRET}", ENCODED, f"user:{ENCODED}", "")
] + [
    f"https://example.invalid/template.git?token={ENCODED}",
    f"https://example.invalid/template.git#{SECRET}",
    "https://example.invalid/template.git?",
    "https://example.invalid/template.git#",
    f"gh:owner/template?token={SECRET}",
    f"gl:owner/template#{SECRET}",
    f"ssh://git:{SECRET}@example.invalid/template.git",
    f"git+ssh://git:{ENCODED}@example.invalid/template.git",
    f"https://{SECRET}%40example.invalid/template.git",
    f"https://[{SECRET}/template.git",
    f"https://example.invalid:{SECRET}/template.git",
    f"https://{SECRET}\\@example.invalid/template.git",
    f"https://example.invalid/\n{SECRET}",
    f"https://example.invalid/%0a{SECRET}",
    f" https://{SECRET}@example.invalid/template.git",
    f"https:{SECRET}@example.invalid/template.git",
]
SAFE = [
    "https://example.invalid/template.git",
    "git+https://example.invalid/template.git",
    "ssh://git@example.invalid/template.git",
    "git+ssh://git@example.invalid:2222/template.git",
    "git@example.invalid:owner/template.git",
    "gh:owner/template",
    "gl:owner/template",
    "../local@template#one",
    "/templates/local?template",
    "./[bold]local-template",
    r"C:\templates\local@template#one",
    r"\\server\share\template",
]


def _assert_hidden(text: str) -> None:
    assert SECRET not in text
    assert ENCODED not in text


def _unexpected(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("Rejected sources must not reach prompts, staging, or Copier")


@pytest.mark.parametrize("source", UNSAFE)
def test_validation_and_display_never_echo_credentials(source: str) -> None:
    with pytest.raises(SourceError) as caught:
        validate_source(source)
    assert "--template-url" in str(caught.value)
    assert "credential" in str(caught.value)
    _assert_hidden(str(caught.value))
    _assert_hidden("".join(traceback.format_exception(caught.value)))
    _assert_hidden(display_source(source))


@pytest.mark.parametrize("source", SAFE)
def test_safe_source_formats_are_accepted(source: str) -> None:
    validate_source(source)


@pytest.mark.parametrize("source", UNSAFE)
@pytest.mark.parametrize("mode", ["continue", "abort", "yes", "dry-run"])
def test_new_rejects_before_prompts_or_effects(
    source: str,
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    for name in ("_select_template", "_collect_answers"):
        monkeypatch.setattr(cli, name, _unexpected)
    monkeypatch.setattr(runner, "scaffold", _unexpected)
    monkeypatch.setattr(typer, "confirm", _unexpected)
    monkeypatch.setattr(runner, "run_copy", _unexpected)
    dst = tmp_path / "untouched"
    args = ["new", "--legacy", "Example", "--template-url", source, "--path", str(dst)]
    if mode in {"yes", "dry-run"}:
        args.append("--yes")
    if mode == "dry-run":
        args.append("--dry-run")
    result = CliRunner().invoke(
        cli.app, args, input="y\n" if mode == "continue" else "n\n"
    )
    assert result.exit_code == 1, result.output
    assert "--template-url" in result.output
    assert "Continue?" not in result.output
    for output in (result.stdout, result.stderr, caplog.text, str(result.exception)):
        _assert_hidden(output)
    assert not dst.exists()


@pytest.mark.parametrize("source", UNSAFE)
def test_direct_scaffold_rejects_before_destination_checks(
    source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(staging, "ensure_available", _unexpected)
    monkeypatch.setattr(runner, "run_copy", _unexpected)
    with pytest.raises(runner.ScaffoldError) as caught:
        runner.scaffold(
            runner.ScaffoldRequest(src=source, dst=tmp_path / "new", data={})
        )
    _assert_hidden(str(caught.value))
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("source", SAFE)
@pytest.mark.parametrize("mode", ["continue", "abort", "yes"])
def test_safe_sources_keep_warning_and_forwarding(
    source: str, mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "_load_config_or_exit", UserConfig)
    monkeypatch.setattr(
        cli, "_collect_answers", lambda *_a, **_k: {"project_name": "Example"}
    )
    monkeypatch.setattr(cli, "_select_template", lambda *_a, **_k: None)
    calls: list[runner.ScaffoldRequest] = []
    monkeypatch.setattr(runner, "scaffold", calls.append)
    args = [
        "new",
        "--legacy",
        "Example",
        "--template-url",
        source,
        "--ref",
        "HEAD",
        "--dry-run",
    ]
    if mode == "yes":
        args.append("--yes")
    result = CliRunner().invoke(
        cli.app, args, input="n\n" if mode == "abort" else "y\n"
    )
    assert result.exit_code == (130 if mode == "abort" else 0), result.output
    assert "Template code will be executed" in result.output
    if mode == "abort":
        assert not calls
    else:
        assert calls[0].src == source
        assert calls[0].vcs_ref == "HEAD"


def test_warning_renders_source_as_literal_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    console = Console(width=180, record=True)
    monkeypatch.setattr(cli, "err", console)
    cli._confirm_third_party("./[bold]local-template", yes=True)
    assert "./[bold]local-template" in console.export_text()
    cli._confirm_third_party(
        f"https://user:{ENCODED}@example.invalid/t?{SECRET}", yes=True
    )
    _assert_hidden(console.export_text())


@pytest.mark.parametrize("source", UNSAFE)
@pytest.mark.parametrize("dry_run", [False, True])
def test_update_rejects_recorded_sources_without_changes(
    source: str, dry_run: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = tmp_path / ".copier-answers.yml"
    before = yaml.safe_dump({"_src_path": source, "_commit": "v1.0.0"}).encode()
    answers.write_bytes(before)
    monkeypatch.setattr(runner, "run_update", _unexpected)
    with pytest.raises(runner.ScaffoldError) as caught:
        runner.update(tmp_path, dry_run=dry_run)
    assert ".copier-answers.yml _src_path" in str(caught.value)
    _assert_hidden(str(caught.value))
    assert answers.read_bytes() == before
    assert list(tmp_path.iterdir()) == [answers]


@pytest.mark.parametrize(
    "content",
    [
        "",
        "[]",
        "{}",
        "_src_path: 123",
        "_src_path: null",
        "_src_path: ''",
        f"_src_path: [{SECRET}",
    ],
)
def test_update_metadata_errors_do_not_echo_yaml(
    content: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = tmp_path / ".copier-answers.yml"
    answers.write_text(content, encoding="utf-8")
    monkeypatch.setattr(runner, "run_update", _unexpected)
    result = CliRunner().invoke(cli.app, ["update", str(tmp_path)])
    assert result.exit_code == 1, result.output
    assert ".copier-answers.yml" in result.output
    _assert_hidden(result.stdout + result.stderr)
    assert answers.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("operation", ["new", "update"])
@pytest.mark.parametrize("process", [False, True])
def test_downstream_failure_text_is_not_rendered(
    operation: str,
    process: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = (
        ProcessExecutionError(["git", SECRET], 128, SECRET, ENCODED)
        if process
        else CopierError(f"unexpected {SECRET} {ENCODED}")
    )

    def fail(**_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(runner, "run_copy", fail)
    monkeypatch.setattr(runner, "run_update", fail)
    monkeypatch.setattr(cli, "_load_config_or_exit", UserConfig)
    if operation == "new":
        args = [
            "new",
            "--legacy",
            "Example",
            "--yes",
            "--path",
            str(tmp_path / "new"),
            "--template-url",
            SAFE[0],
        ]
    else:
        (tmp_path / ".copier-answers.yml").write_text(
            yaml.safe_dump({"_src_path": SAFE[0]}), encoding="utf-8"
        )
        args = ["update", str(tmp_path)]
    result = CliRunner().invoke(cli.app, args)
    assert result.exit_code == 1, result.output
    assert "could not complete" in result.output
    _assert_hidden(result.stdout + result.stderr + caplog.text)
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("operation", ["new", "update"])
def test_real_console_does_not_render_rejected_sources(
    operation: str, tmp_path: Path, create_forge_command: str
) -> None:
    source = f"https://user:{ENCODED}@example.invalid/template.git"
    if operation == "new":
        args = [
            "new",
            "--legacy",
            "Example",
            "--yes",
            "--template-url",
            source,
            "--path",
            str(tmp_path / "new"),
        ]
    else:
        (tmp_path / ".copier-answers.yml").write_text(
            yaml.safe_dump({"_src_path": source}), encoding="utf-8"
        )
        args = ["update", str(tmp_path)]
    result = subprocess.run(  # noqa: S603 -- resolved installed console and test data
        [create_forge_command, *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 1
    _assert_hidden(result.stdout + result.stderr)
    assert "Traceback" not in result.stdout + result.stderr
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("source", SAFE)
def test_update_keeps_accepted_source_metadata(
    source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = tmp_path / ".copier-answers.yml"
    before = yaml.safe_dump({"_src_path": source}).encode()
    answers.write_bytes(before)
    calls: list[dict[str, object]] = []

    def record(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(runner, "run_update", record)
    runner.update(tmp_path, vcs_ref="HEAD", dry_run=True)
    assert len(calls) == 1
    assert calls[0]["vcs_ref"] == "HEAD"
    assert calls[0]["pretend"] is True
    assert answers.read_bytes() == before
