"""CLI behaviour via Typer's CliRunner.

`scaffold` is monkeypatched with a recorder so these assert the resolved
`ScaffoldRequest` rather than actually invoking Copier -- `ScaffoldRequest` is
frozen/slots, so it compares by value. The real console script, a real
scaffold, and generated-project checks are covered by
`tests/test_e2e_generation.py` (CF-07.06), not this fast suite; the three
conflict/cleanup cases below use the real `scaffold` with only
`runner.run_copy` faked, matching `tests/test_runner.py`'s style, to prove
the same behaviour at the CLI layer without paying for a real clone.
"""

from __future__ import annotations

import builtins
import importlib.metadata
import json
from importlib.metadata import PackageNotFoundError
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest
import typer
from copier.errors import CopierError
from forge_template import (
    ComponentOwner,
    EngineInfo,
    GenerationPlan,
    PlannedFile,
    RenderedFile,
    RenderedProject,
)
from pydantic import HttpUrl
from rich.console import Console
from typer.testing import CliRunner

import create_forge.cli as cli_module
import create_forge.runner as runner_module
import create_forge.staging as staging_module
from create_forge import engine as engine_module
from create_forge import pipeline as pipeline_module
from create_forge.cli import _markers, app
from create_forge.config import UserConfig, config_path
from create_forge.models import Registry, Template
from create_forge.pipeline import GenerationRequest
from create_forge.prompts import PromptAbortedError
from create_forge.registry import load_registry
from create_forge.runner import ScaffoldError, ScaffoldRequest
from create_forge.staging import StagingError

if TYPE_CHECKING:
    from collections.abc import Mapping

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


@pytest.fixture
def update_recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Path, str | None, bool]]:
    calls: list[tuple[Path, str | None, bool]] = []

    def fake_update(
        project: Path, *, vcs_ref: str | None = None, dry_run: bool = False
    ) -> None:
        calls.append((project, vcs_ref, dry_run))

    monkeypatch.setattr(cli_module, "update", fake_update)
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


def _hide_engine_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force `importlib.metadata.version("forge-template")` to raise, as it
    would in a real environment without the `engine` extra installed --
    deterministic regardless of whether *this* dev checkout happens to have
    `--all-extras` resolved. Every other distribution resolves normally.
    """

    def fake(name: str) -> str:
        if name == "forge-template":
            raise PackageNotFoundError(name)
        return importlib.metadata.version(name)

    monkeypatch.setattr(cli_module, "version", fake)


def _show_engine_extra(monkeypatch: pytest.MonkeyPatch, installed_version: str) -> None:
    """The inverse of `_hide_engine_extra`: force a specific installed
    `forge-template` version, deterministic regardless of the ambient venv.
    """

    def fake(name: str) -> str:
        if name == "forge-template":
            return installed_version
        return importlib.metadata.version(name)

    monkeypatch.setattr(cli_module, "version", fake)


def test_doctor_reports_versions_and_the_engine_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF-04.01's diagnostics contract (docs/engine-resolution.md): doctor
    must report the create-forge and Copier versions plus an explicit engine
    row -- since ADR 0018, always naming the supported range, and the
    installed version when the `engine` extra is present."""
    monkeypatch.setattr(cli_module, "_git_config", lambda _key: "test")
    _hide_engine_extra(monkeypatch)

    result = runner.invoke(app, ["doctor"])

    assert result.exception is None, result.output
    assert "create-forge" in result.output
    assert "copier" in result.output
    assert "not installed" in result.output
    assert "forge-template>=0.3.1,<0.4" in result.output
    assert "engine" in result.output


def test_doctor_reports_the_installed_engine_package_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the row above: when the extra is installed, doctor
    names the installed version, not "not installed"."""
    monkeypatch.setattr(cli_module, "_git_config", lambda _key: "test")
    _show_engine_extra(monkeypatch, "0.3.1")

    result = runner.invoke(app, ["doctor", "--json"])

    payload = json.loads(result.output)
    assert payload["integration"]["engine_package"] == "0.3.1"


def test_doctor_json_emits_the_documented_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`doctor --json` must carry every field docs/engine-resolution.md's
    diagnostics contract documents, print no table, and still exit 0 when
    every check passes."""
    monkeypatch.setattr(cli_module, "_git_config", lambda _key: "test")
    _hide_engine_extra(monkeypatch)
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["create_forge"] == cli_module._version()
    assert payload["ok"] is True
    integration = payload["integration"]
    assert integration["line"] == "v0.2.x-copier"
    assert integration["engine_package"] is None
    assert integration["engine_range"] == "forge-template>=0.3.1,<0.4"
    assert integration["projectspec_protocol"] == {"supported": "1", "detected": None}
    assert integration["template_source"] is not None
    assert {"name", "ok", "detail"} <= payload["checks"][0].keys()
    # The table's own column header must not leak into --json output, and
    # informational rows (already under "integration") must not duplicate
    # into "checks".
    assert "Check" not in result.output
    assert all(c["name"] != "engine" for c in payload["checks"])


def test_doctor_json_exits_1_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `--json` flag changes the output format only -- an unhealthy
    environment must still be reported through the exit status a script
    would check."""
    monkeypatch.setattr(cli_module, "_git_config", lambda _key: "test")

    def _broken_registry() -> object:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli_module, "load_registry", _broken_registry)

    result = runner.invoke(app, ["doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    registry_check = next(c for c in payload["checks"] if c["name"] == "registry")
    assert registry_check["ok"] is False


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


def test_update_dry_run_forwards_ref_and_reports_no_changes(
    update_recorder: list[tuple[Path, str | None, bool]], tmp_path: Path
) -> None:
    project = tmp_path / "project"

    result = runner.invoke(
        app, ["update", str(project), "--ref", "v1.1.0", "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert update_recorder == [(project.resolve(), "v1.1.0", True)]
    assert "Dry run complete." in result.output
    assert "No project files changed." in result.output
    assert "Updated." not in result.output


def test_update_without_dry_run_preserves_current_behavior(
    update_recorder: list[tuple[Path, str | None, bool]], tmp_path: Path
) -> None:
    project = tmp_path / "project"

    result = runner.invoke(app, ["update", str(project)])

    assert result.exit_code == 0, result.output
    assert update_recorder == [(project.resolve(), None, False)]
    assert "Updated." in result.output
    assert "Review the diff before committing" in result.output
    assert "Dry run complete." not in result.output


def test_update_failure_exits_1_without_a_success_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fail_update(
        _project: Path, *, vcs_ref: str | None = None, dry_run: bool = False
    ) -> None:
        del vcs_ref, dry_run
        raise ScaffoldError("update failed")

    monkeypatch.setattr(cli_module, "update", fail_update)

    result = runner.invoke(app, ["update", str(tmp_path / "project"), "--dry-run"])

    assert result.exit_code == 1
    assert "update failed" in result.output
    assert "Updated." not in result.output
    assert "Dry run complete." not in result.output


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
    assert result.exit_code == 2
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


def test_new_template_url_accepted_forwards_local_source_ref_and_warning(
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
            "../forge-template",
            "--ref",
            "HEAD",
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder[0].src == "../forge-template"
    assert recorder[0].vcs_ref == "HEAD"
    assert "Template code will be executed" in result.output
    assert "Only continue if you trust it" in result.output


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


# --- CF-07.06: conflict and cleanup, at the CLI layer ------------------------
#
# The real `scaffold()` runs here (no `recorder` fixture) with only
# `runner.run_copy` faked -- these prove `staging.py`'s conflict/cleanup
# integration (already unit-tested by tests/test_runner.py) also holds
# through `new`'s actual command wiring, without a real Copier clone.


def test_new_rejects_a_non_empty_destination_before_copier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "existing.txt").write_text("hi", encoding="utf-8")

    def unexpected_run_copy(**_kwargs: object) -> None:
        raise AssertionError("run_copy must not run against a non-empty destination")

    monkeypatch.setattr(runner_module, "run_copy", unexpected_run_copy)

    result = runner.invoke(app, ["new", "Foo", "--yes", "--path", str(dest)])

    assert result.exit_code == 1, result.output
    normalised_output = " ".join(result.output.split())
    assert "already exists and is not empty" in normalised_output
    assert (dest / "existing.txt").read_text(encoding="utf-8") == "hi"


def test_new_removes_a_destination_it_created_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"

    def failing_run_copy(**kwargs: object) -> None:
        # A realistic partial Copier run: some output landed before Copier
        # itself failed.
        Path(str(kwargs["dst_path"])).mkdir(parents=True, exist_ok=True)
        (Path(str(kwargs["dst_path"])) / "partial.txt").write_text(
            "x", encoding="utf-8"
        )
        raise CopierError("simulated render failure")

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)

    result = runner.invoke(app, ["new", "Foo", "--yes", "--path", str(dest)])

    assert result.exit_code == 1, result.output
    assert not dest.exists()


def test_new_leaves_a_pre_existing_destination_untouched_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    dest.mkdir()  # exists and is empty -- a legitimate --path target

    def failing_run_copy(**_kwargs: object) -> None:
        raise CopierError("simulated render failure")

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)

    result = runner.invoke(app, ["new", "Foo", "--yes", "--path", str(dest)])

    assert result.exit_code == 1, result.output
    assert dest.is_dir()
    assert list(dest.iterdir()) == []


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


# --- --engine-preview (CF-07.01 / #49, ADR 0014) ------------------------------

_ENGINE_PREVIEW_ANSWERS = [
    "--data",
    "github_org=test-org",
    "--data",
    "license=mit",
    "--data",
    "author_name=Test User",
    "--data",
    "author_email=test@example.invalid",
    "--data",
    "python_min_version=3.11",
    "--data",
    "python_version=3.13",
    # A default archetype (CF-08.02): individual tests override this by
    # appending a later --archetype, which wins under Click's last-flag-wins
    # rule for a scalar option.
    "--archetype",
    "library",
]


def test_new_without_engine_preview_is_unchanged(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """The hidden flag defaults to False; every existing test above already
    proves this, but this makes the default explicit and future-proof.
    """
    result = runner.invoke(
        app, ["new", "Foo", "--yes", "--path", str(tmp_path / "proj")]
    )

    assert result.exit_code == 0, result.output
    assert len(recorder) == 1
    assert "Engine preview" not in result.output


def test_new_engine_preview_fails_cleanly_without_the_engine_dependency(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """Simulates a real `uvx create-forge` install, where forge-template is
    not installed at all. cli.py's lazy import must fail cleanly rather than
    crash the whole command with a raw traceback -- and must never fall back
    to actually scaffolding.

    Blocking via `sys.modules["forge_template"] = None` alone is not
    reliable here: `create_forge.engine`/`create_forge.pipeline` are already
    imported by other test modules in this same process, and CPython's
    `from package import submodule` machinery can satisfy that from the
    parent package's already-set `submodule` attribute without re-executing
    the submodule at all, even after deleting it from `sys.modules`.
    Patching `builtins.__import__` intercepts the actual import call
    `cli.py` makes, regardless of caching.
    """
    real_import = builtins.__import__

    def blocking_import(
        name: str,
        globals: Mapping[str, object] | None = None,  # noqa: A002 - matches __import__
        locals: Mapping[str, object] | None = None,  # noqa: A002 - matches __import__
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "create_forge" and "pipeline" in fromlist:
            msg = "forge_template not installed (simulated)"
            raise ImportError(msg)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocking_import)

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(tmp_path / "proj"),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "engine extra isn't installed" in result.output
    assert recorder == []
    assert not (tmp_path / "proj").exists()


def test_new_engine_preview_generates_a_real_cli_application(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[ScaffoldRequest],
    tmp_path: Path,
) -> None:
    """The real, unmocked engine: `forge-template` 0.3.0's production
    catalogue makes `--engine-preview` generate for real (CF-08.02),
    superseding the Stage 06-era empty-catalogue rejection this test
    replaces -- see
    `tests/test_pipeline.py::test_build_generation_request_succeeds_against_the_real_catalogue`
    for the equivalent pipeline-level proof.
    """
    dest = tmp_path / "proj"

    def fake_lock(staging_dir: Path) -> None:
        (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setattr(staging_module, "create_uv_lock", fake_lock)

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
            "--archetype",
            "cli",
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder == []
    assert (dest / "src" / "engine_preview" / "cli.py").exists()
    assert (dest / "uv.lock").is_file()
    pyproject = (dest / "pyproject.toml").read_text(encoding="utf-8")
    assert 'engine-preview = "engine_preview.cli:app"' in pyproject


def test_new_engine_preview_exits_3_on_incompatible_engine(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    monkeypatch.setattr(
        engine_module,
        "get_engine_info",
        lambda: EngineInfo(
            package_version="9.0.0",
            projectspec_protocols=(99,),
            component_manifest_protocols=(1,),
        ),
    )

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(tmp_path / "proj"),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
        ],
    )

    assert result.exit_code == 3, result.output
    assert recorder == []
    assert not (tmp_path / "proj").exists()


def test_new_engine_preview_rejects_a_non_empty_destination_before_the_engine(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """ADR 0015: the destination conflict is checked before the engine is
    even imported, let alone negotiated or validated against.
    """
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "existing.txt").write_text("hi", encoding="utf-8")

    def unexpected_get_engine_info() -> EngineInfo:
        raise AssertionError("the engine must not be reached for a conflict")

    monkeypatch.setattr(engine_module, "get_engine_info", unexpected_get_engine_info)

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
        ],
    )

    assert result.exit_code == 1, result.output
    # Rich wraps long lines to the console width, which varies by
    # environment (narrower in CI than a local wide terminal) -- normalise
    # whitespace before matching so a mid-phrase line break can't fail this.
    normalised_output = " ".join(result.output.split())
    assert "already exists and is not empty" in normalised_output
    assert recorder == []
    assert (dest / "existing.txt").read_text(encoding="utf-8") == "hi"


def test_new_engine_preview_dry_run_lists_targets_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """`--dry-run` short-circuits before staging (ADR 0015).
    `build_generation_request` is faked here with a successful result --
    the same technique test_pipeline.py uses -- so this exercises the
    dry-run branch in isolation from a real render.
    """
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda _root: pytest.fail("dry-run must not create a lockfile"),
    )

    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "pyproject.toml" in result.output
    assert recorder == []
    assert not dest.exists()


def test_new_engine_preview_finalises_a_successful_render(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """A successful (faked) render is staged and moved into place exactly
    like the Copier path, and reports success without claiming the project
    is `create-forge update`-able (ADR 0015).
    """
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )

    def fake_lock(staging_dir: Path) -> None:
        (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setattr(staging_module, "create_uv_lock", fake_lock)

    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
        ],
    )

    assert result.exit_code == 0, result.output
    assert recorder == []
    assert (dest / "pyproject.toml").read_bytes() == b"[project]\n"
    assert (dest / "uv.lock").is_file()
    assert "created at" in result.output
    # Normalise whitespace: Rich wraps long lines to the console width,
    # which varies by environment (see the destination-conflict test above).
    normalised_output = " ".join(result.output.split())
    assert "create-forge update does not apply" in normalised_output
    assert "uv run --locked poe check" in normalised_output


def test_new_engine_preview_reports_lock_failure_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    recorder: list[ScaffoldRequest],
    tmp_path: Path,
) -> None:
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=ComponentOwner(id="library")),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
    )
    fake_request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    monkeypatch.setattr(
        pipeline_module, "build_generation_request", lambda *a, **k: fake_request
    )

    def failing_lock(_root: Path) -> None:
        raise StagingError("uv lock failed")

    monkeypatch.setattr(staging_module, "create_uv_lock", failing_lock)
    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "uv lock failed" in result.output
    assert recorder == []
    assert not dest.exists()


def test_new_archetype_without_engine_preview_is_rejected(
    recorder: list[ScaffoldRequest],
) -> None:
    """`--archetype` is meaningless on the Copier path (CF-08.02); passing it
    without `--engine-preview` must not be silently ignored.
    """
    result = runner.invoke(app, ["new", "Foo", "--yes", "--archetype", "cli"])

    assert result.exit_code == 1, result.output
    assert "--archetype requires --engine-preview" in result.output
    assert recorder == []


def test_new_engine_preview_yes_without_archetype_is_rejected(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """`--yes` has no interactive fallback and the engine declares no
    default archetype (CF-08.02) -- omitting `--archetype` must fail, not
    silently pick one.
    """
    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            "--data",
            "github_org=test-org",
            "--data",
            "license=mit",
            "--data",
            "author_name=Test User",
            "--data",
            "author_email=test@example.invalid",
            "--data",
            "python_min_version=3.11",
            "--data",
            "python_version=3.13",
            "--engine-preview",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "--yes" in result.output
    assert "requires --archetype" in result.output
    assert "cli" in result.output
    assert "library" in result.output
    assert recorder == []
    assert not dest.exists()


def test_new_engine_preview_unknown_archetype_is_rejected(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    dest = tmp_path / "proj"

    result = runner.invoke(
        app,
        [
            "new",
            "Engine Preview",
            "--yes",
            "--path",
            str(dest),
            *_ENGINE_PREVIEW_ANSWERS,
            "--engine-preview",
            "--archetype",
            "nonexistent",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "Unknown archetype 'nonexistent'" in result.output
    assert recorder == []
    assert not dest.exists()


def test_new_engine_preview_prompts_when_archetype_is_omitted(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """Without `--yes` or `--archetype`, selection falls to an interactive
    prompt over the real discovered catalogue (CF-08.02) -- mirroring
    `test_new_interactive_resolves_template_and_answers`'s style of
    monkeypatching the prompt functions themselves rather than driving real
    stdin through questionary. Template selection and answer collection are
    likewise faked here: only archetype selection is under test.
    """
    registry = load_registry()
    template = registry.get(registry.default_template)
    monkeypatch.setattr(cli_module, "choose_template", lambda *_a, **_kw: template)
    monkeypatch.setattr(
        cli_module,
        "ask_all",
        lambda *_a, **_kw: {
            "project_name": "Engine Preview",
            "github_org": "test-org",
            "license": "mit",
            "author_name": "Test User",
            "author_email": "test@example.invalid",
            "python_min_version": "3.11",
            "python_version": "3.13",
        },
    )

    seen_archetypes: list[str] = []

    def fake_choose_archetype(archetypes: object) -> object:
        ids = [a.id for a in archetypes]  # type: ignore[attr-defined]
        seen_archetypes.extend(ids)
        return next(a for a in archetypes if a.id == "cli")  # type: ignore[attr-defined]

    monkeypatch.setattr(cli_module, "choose_archetype", fake_choose_archetype)

    dest = tmp_path / "proj"

    result = runner.invoke(app, ["new", "--path", str(dest), "--engine-preview"])

    assert result.exit_code == 0, result.output
    assert {"library", "cli"} <= set(seen_archetypes)
    assert recorder == []
    assert (dest / "src" / "engine_preview" / "cli.py").exists()


def test_new_engine_preview_aborting_archetype_choice_exits_130(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """Mirrors `test_new_aborting_the_template_choice_exits_130`'s shape for
    the new archetype prompt (CF-08.02). Template selection and answer
    collection are faked, same as the interactive-selection test above, so
    only the abort itself is under test.
    """
    registry = load_registry()
    template = registry.get(registry.default_template)
    monkeypatch.setattr(cli_module, "choose_template", lambda *_a, **_kw: template)
    monkeypatch.setattr(
        cli_module,
        "ask_all",
        lambda *_a, **_kw: {
            "project_name": "Engine Preview",
            "github_org": "test-org",
            "license": "mit",
            "author_name": "Test User",
            "author_email": "test@example.invalid",
            "python_min_version": "3.11",
            "python_version": "3.13",
        },
    )

    def _abort(*_args: object, **_kwargs: object) -> object:
        raise PromptAbortedError

    monkeypatch.setattr(cli_module, "choose_archetype", _abort)

    dest = tmp_path / "proj"

    result = runner.invoke(app, ["new", "--path", str(dest), "--engine-preview"])

    assert result.exit_code == 130, result.output
    assert recorder == []
    assert not dest.exists()


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
