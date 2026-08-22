"""CLI behaviour via Typer's CliRunner.

`scaffold` is monkeypatched with a recorder so these assert the resolved
`ScaffoldRequest` rather than actually invoking Copier -- `ScaffoldRequest` is
frozen/slots, so it compares by value. The one real network scaffold lives in
docs/plan-v0.1.0.md's manual verification steps, not in this fast suite.
"""

from __future__ import annotations

from io import BytesIO, TextIOWrapper
from pathlib import Path

import pytest
import typer
from pydantic import HttpUrl
from rich.console import Console
from typer.testing import CliRunner

import create_forge.cli as cli_module
from create_forge.cli import _markers, app
from create_forge.config import UserConfig, config_path
from create_forge.models import Registry, Template
from create_forge.prompts import PromptAbortedError
from create_forge.registry import load_registry
from create_forge.runner import ScaffoldError, ScaffoldRequest

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point config_path() at a throwaway directory with no FORGE_* leakage.

    Without this, `new`/`doctor`/`config` would read the developer's real
    ~/.config/create-forge/config.toml and environment, making these tests
    depend on who runs them -- the same reasoning as test_config.py's
    _clean_forge_env, extended to also isolate the file path.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for field in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{field.upper()}", raising=False)
    return config_path()


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> list[ScaffoldRequest]:
    calls: list[ScaffoldRequest] = []

    def fake_scaffold(request: ScaffoldRequest) -> None:
        calls.append(request)

    # Patch the name inside cli, not runner -- cli.py imports scaffold
    # directly, so patching create_forge.runner.scaffold would not affect
    # the reference `new()` actually calls.
    monkeypatch.setattr(cli_module, "scaffold", fake_scaffold)
    return calls


def _write_config(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def test_list_shows_the_bundled_templates() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "library" in result.output


def test_doctor_reports_on_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """doctor exits 1 when any check is unhealthy, and a fresh CI runner has
    no global git identity configured -- unlike the author's own machine,
    where this always happened to pass. Monkeypatch it so the test verifies
    doctor's registry reporting, not the host's git config."""
    monkeypatch.setattr(cli_module, "_git_config", lambda _key: "test")
    result = runner.invoke(app, ["doctor"])
    assert result.exception is None
    assert "registry" in result.output


def test_doctor_survives_a_console_that_cannot_encode_check_marks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for #12: a Windows console on the cp1252 codepage --
    the default outside Windows Terminal -- cannot encode the check-mark
    glyphs doctor's table used unconditionally, and Rich let the resulting
    UnicodeEncodeError propagate instead of degrading. CliRunner's own output
    capture goes through UTF-8, so this has to install a real cp1252 console
    to reproduce the crash; test_doctor_reports_on_the_registry above never
    could have caught this."""
    monkeypatch.setattr(cli_module, "_git_config", lambda _key: "test")
    cp1252_console = Console(file=TextIOWrapper(BytesIO(), encoding="cp1252"), width=80)
    monkeypatch.setattr(cli_module, "console", cp1252_console)

    result = runner.invoke(app, ["doctor"])

    assert result.exception is None, result.output


def test_markers_are_ascii_when_the_encoding_cannot_take_glyphs() -> None:
    cp1252_console = Console(file=TextIOWrapper(BytesIO(), encoding="cp1252"), width=80)

    assert _markers(cp1252_console) == ("OK", "FAIL")


def test_markers_use_glyphs_when_the_encoding_allows() -> None:
    """The cp1252 fallback must not flatten output for consoles that can
    render the real glyphs -- fixing this for some users should not cost
    everyone else the nicer marks."""
    utf8_console = Console(file=TextIOWrapper(BytesIO(), encoding="utf-8"), width=80)

    assert _markers(utf8_console) == ("✓", "✗")


def test_new_dry_run_records_the_request_and_writes_nothing(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "new",
            "My Project",
            "--yes",
            "--dry-run",
            "--path",
            str(dest),
            "--data",
            "project_description=x",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(recorder) == 1
    request = recorder[0]
    assert request.dry_run is True
    assert request.dst == dest.resolve()
    assert request.data["project_name"] == "My Project"
    assert not dest.exists()


def test_new_data_coerces_true_and_false_to_bool(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "Bool Project",
            "--yes",
            "--dry-run",
            "--path",
            str(tmp_path / "proj"),
            "--data",
            "use_docs=true",
            "--data",
            "some_flag=FALSE",
        ],
    )

    assert result.exit_code == 0, result.output
    request = recorder[0]
    assert request.data["use_docs"] is True
    assert request.data["some_flag"] is False


def test_new_yes_without_a_project_name_is_rejected(
    recorder: list[ScaffoldRequest],
) -> None:
    result = runner.invoke(app, ["new", "--yes"])
    assert result.exit_code == 1
    assert recorder == []


def test_new_bad_data_format_is_rejected(recorder: list[ScaffoldRequest]) -> None:
    result = runner.invoke(app, ["new", "X", "--yes", "--data", "no-equals-sign"])
    assert result.exit_code != 0
    assert recorder == []


def test_new_unknown_template_exits_with_an_explanation(
    recorder: list[ScaffoldRequest],
) -> None:
    result = runner.invoke(app, ["new", "X", "--yes", "--template", "does-not-exist"])
    assert result.exit_code == 1
    assert recorder == []
    assert "unknown template" in result.output


# --- characterization tests for #16 (extract helpers from cli.new()) --------
#
# These pin the current behaviour of the interactive/third-party/reporting
# branches -- everything test_new_dry_run_records_the_request_and_writes_nothing
# and its neighbours above never touch, since they all run --yes --dry-run.
# They must pass against cli.py both before and after the #16 refactor: a
# failure here before the refactor is a bug in the test, not a discovered
# defect.


def _deprecated_registry() -> Registry:
    """A synthetic two-template registry: the bundled one has no deprecated
    entry, and _deprecation_has_successor requires a successor to exist."""
    return Registry(
        default_template="library",
        templates=[
            Template(
                id="library",
                name="Library",
                description="stable",
                url=HttpUrl("https://example.com/library"),
                status="stable",
            ),
            Template(
                id="legacy",
                name="Legacy",
                description="old",
                url=HttpUrl("https://example.com/legacy"),
                status="deprecated",
                deprecated_in_favour_of="library",
            ),
        ],
    )


def test_new_interactive_resolves_template_and_answers(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = load_registry()
    template = registry.get(registry.default_template)
    monkeypatch.setattr(cli_module, "choose_template", lambda *_a, **_kw: template)
    monkeypatch.setattr(
        cli_module,
        "ask_all",
        lambda *_a, **_kw: {
            "project_name": "Interactive Project",
            "project_description": "d",
        },
    )

    result = runner.invoke(app, ["new", "--path", str(tmp_path / "proj")])

    assert result.exit_code == 0, result.output
    assert len(recorder) == 1
    request = recorder[0]
    assert request.src == str(template.url)
    assert request.data["project_name"] == "Interactive Project"


def test_new_aborting_the_template_choice_exits_130(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _abort(*_args: object, **_kwargs: object) -> None:
        raise PromptAbortedError

    monkeypatch.setattr(cli_module, "choose_template", _abort)

    result = runner.invoke(app, ["new"])

    assert result.exit_code == 130
    assert recorder == []


def test_new_aborting_the_answers_exits_130(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _abort(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise PromptAbortedError

    monkeypatch.setattr(cli_module, "ask_all", _abort)

    result = runner.invoke(app, ["new"])

    assert result.exit_code == 130
    assert recorder == []
    assert "Cancelled" in result.output


def test_new_warns_about_a_deprecated_template(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli_module, "load_registry", _deprecated_registry)

    result = runner.invoke(
        app,
        [
            "new",
            "Legacy Project",
            "--yes",
            "--dry-run",
            "--template",
            "legacy",
            "--path",
            str(tmp_path / "proj"),
            "--data",
            "project_description=x",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "deprecated" in result.output
    assert recorder[0].src == "https://example.com/legacy"


def test_new_template_url_declined_scaffolds_nothing(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli_module,
        "ask_all",
        lambda *_a, **_kw: {"project_name": "Foo", "project_description": "d"},
    )
    monkeypatch.setattr(typer, "confirm", lambda *_a, **_kw: False)

    result = runner.invoke(
        app, ["new", "Foo", "--template-url", "https://example.com/other-template"]
    )

    assert result.exit_code == 130
    assert recorder == []


def test_new_template_url_accepted_uses_that_url(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        cli_module,
        "ask_all",
        lambda *_a, **_kw: {"project_name": "Foo", "project_description": "d"},
    )
    monkeypatch.setattr(typer, "confirm", lambda *_a, **_kw: True)

    result = runner.invoke(
        app,
        [
            "new",
            "Foo",
            "--dry-run",
            "--path",
            str(tmp_path / "proj"),
            "--template-url",
            "https://example.com/other-template",
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder[0].src == "https://example.com/other-template"


def test_new_reports_a_scaffold_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fail(_request: ScaffoldRequest) -> None:
        raise ScaffoldError("boom")

    monkeypatch.setattr(cli_module, "scaffold", _fail)

    result = runner.invoke(
        app, ["new", "Foo", "--yes", "--path", str(tmp_path / "proj")]
    )

    assert result.exit_code == 1
    assert "boom" in result.output


def test_new_reports_where_the_project_was_created(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Foo",
            "--yes",
            "--path",
            str(dest),
            "--data",
            "project_description=x",
        ],
    )

    assert result.exit_code == 0, result.output
    assert len(recorder) == 1
    # Not the full absolute path: pytest's tmp_path is long enough that Rich's
    # panel hard-wraps it across lines, re-bordering each line with "|" --
    # unlike test_new_unknown_default_template_names_the_config_path's target,
    # collapsing newlines alone does not reconstruct it. The directory name is
    # short and stable, and still proves the destination reached the report.
    assert "created at" in result.output
    assert dest.name in result.output


# --- config wiring (issue #3) ------------------------------------------------


def test_new_config_reaches_scaffold_data(
    recorder: list[ScaffoldRequest], _isolated_config: Path, tmp_path: Path
) -> None:
    _write_config(
        _isolated_config,
        'author_name = "Config Author"\ngithub_org = "config-org"\n',
    )

    result = runner.invoke(
        app,
        [
            "new",
            "Demo",
            "--yes",
            "--dry-run",
            "--path",
            str(tmp_path / "demo"),
            "--data",
            "project_description=x",
        ],
    )

    assert result.exit_code == 0, result.output
    data = recorder[0].data
    assert data["author_name"] == "Config Author"
    assert data["github_org"] == "config-org"


def test_new_data_overrides_config(
    recorder: list[ScaffoldRequest], _isolated_config: Path, tmp_path: Path
) -> None:
    _write_config(_isolated_config, 'github_org = "config-org"\n')

    result = runner.invoke(
        app,
        [
            "new",
            "Demo",
            "--yes",
            "--dry-run",
            "--path",
            str(tmp_path / "demo"),
            "--data",
            "project_description=x",
            "--data",
            "github_org=override-org",
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder[0].data["github_org"] == "override-org"


def test_new_malformed_config_is_a_user_error(
    _isolated_config: Path, recorder: list[ScaffoldRequest]
) -> None:
    _write_config(_isolated_config, "not = [valid toml")

    result = runner.invoke(app, ["new", "X", "--yes"])

    assert result.exit_code == 1
    assert recorder == []
    assert "not valid TOML" in result.output


def test_new_unknown_default_template_names_the_config_path(
    _isolated_config: Path, recorder: list[ScaffoldRequest]
) -> None:
    _write_config(_isolated_config, 'default_template = "does-not-exist"\n')

    result = runner.invoke(app, ["new", "X", "--yes"])

    # Rich wraps long lines in CliRunner's fixed-width capture, so compare
    # with newlines collapsed rather than requiring one contiguous substring.
    flattened = result.output.replace("\n", "")

    assert result.exit_code == 1
    assert recorder == []
    assert str(_isolated_config) in flattened
    assert "does-not-exist" in flattened


def test_config_init_writes_the_example_file(_isolated_config: Path) -> None:
    assert not _isolated_config.exists()

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0, result.output
    assert _isolated_config.exists()


def test_config_init_never_overwrites(_isolated_config: Path) -> None:
    _write_config(_isolated_config, "custom content")

    result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0, result.output
    assert _isolated_config.read_text(encoding="utf-8") == "custom content"


def test_config_show_reports_resolved_values(_isolated_config: Path) -> None:
    _write_config(_isolated_config, 'author_name = "Config Author"\n')

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert "Config Author" in result.output
    assert "config file" in result.output


def test_config_show_reports_environment_source(
    _isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_GITHUB_ORG", "env-org")

    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, result.output
    assert "env-org" in result.output
    assert "environment" in result.output
