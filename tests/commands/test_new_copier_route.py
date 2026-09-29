"""`commands/new.py` -- the `--legacy` (Copier) route: `new`'s legacy branch
plus the helpers only it reaches (`_select_template`, `_collect_answers`,
`_run_scaffold`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from copier.errors import CopierError
from pydantic import HttpUrl
from typer.testing import CliRunner

import create_forge.runner as runner_module
from create_forge.cli import app
from create_forge.commands import new as new_module
from create_forge.models import Registry, Template
from create_forge.prompts import PromptAbortedError
from create_forge.registry import load_registry
from create_forge.runner import ScaffoldError, ScaffoldRequest
from tests.commands.support import write_config
from tests.staging_probe import staging_siblings

runner = CliRunner()


def test_new_dry_run_records_the_request_and_writes_nothing(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "new",
            "--legacy",
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
            "--legacy",
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
    result = runner.invoke(app, ["new", "--legacy", "--yes"])
    assert result.exit_code == 1
    assert recorder == []


def test_new_bad_data_format_is_rejected(recorder: list[ScaffoldRequest]) -> None:
    result = runner.invoke(
        app, ["new", "--legacy", "X", "--yes", "--data", "no-equals-sign"]
    )
    assert result.exit_code == 2
    assert recorder == []


def test_new_unknown_template_exits_with_an_explanation(
    recorder: list[ScaffoldRequest],
) -> None:
    result = runner.invoke(
        app, ["new", "--legacy", "X", "--yes", "--template", "does-not-exist"]
    )
    assert result.exit_code == 1
    assert recorder == []
    assert "unknown template" in result.output


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
    monkeypatch.setattr(new_module, "choose_template", lambda *_a, **_kw: template)
    monkeypatch.setattr(
        new_module,
        "ask_all",
        lambda *_a, **_kw: {
            "project_name": "Interactive Project",
            "project_description": "d",
        },
    )

    result = runner.invoke(app, ["new", "--legacy", "--path", str(tmp_path / "proj")])

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

    monkeypatch.setattr(new_module, "choose_template", _abort)

    result = runner.invoke(app, ["new", "--legacy"])

    assert result.exit_code == 130
    assert recorder == []


def test_new_aborting_the_answers_exits_130(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _abort(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise PromptAbortedError

    monkeypatch.setattr(new_module, "ask_all", _abort)

    result = runner.invoke(app, ["new", "--legacy"])

    assert result.exit_code == 130
    assert recorder == []
    assert "Cancelled" in result.output


def test_new_warns_about_a_deprecated_template(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(new_module, "load_registry", _deprecated_registry)

    result = runner.invoke(
        app,
        [
            "new",
            "--legacy",
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
        new_module,
        "ask_all",
        lambda *_a, **_kw: {"project_name": "Foo", "project_description": "d"},
    )
    monkeypatch.setattr(typer, "confirm", lambda *_a, **_kw: False)

    result = runner.invoke(
        app,
        [
            "new",
            "--legacy",
            "Foo",
            "--template-url",
            "https://example.com/other-template",
        ],
    )

    assert result.exit_code == 130
    assert recorder == []


def test_new_template_url_accepted_forwards_local_source_ref_and_warning(
    recorder: list[ScaffoldRequest], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        new_module,
        "ask_all",
        lambda *_a, **_kw: {"project_name": "Foo", "project_description": "d"},
    )
    monkeypatch.setattr(typer, "confirm", lambda *_a, **_kw: True)

    result = runner.invoke(
        app,
        [
            "new",
            "--legacy",
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

    monkeypatch.setattr(runner_module, "scaffold", _fail)

    result = runner.invoke(
        app, ["new", "--legacy", "Foo", "--yes", "--path", str(tmp_path / "proj")]
    )

    assert result.exit_code == 1
    assert "boom" in result.output


def test_new_legacy_credential_bearing_template_url_is_rejected(
    recorder: list[ScaffoldRequest],
) -> None:
    """A credential-bearing `--template-url` is rejected before any clone
    (ADR 0036) -- `new --legacy`'s own call to `validate_source`, distinct
    from `update`'s `_src_path` re-validation `tests/test_sources.py` covers.
    """
    result = runner.invoke(
        app,
        [
            "new",
            "--legacy",
            "Foo",
            "--yes",
            "--template-url",
            "https://user:secret@example.com/template.git",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "secret" not in result.output
    assert recorder == []


def test_new_rejects_a_non_empty_destination_before_copier(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    dest.mkdir()
    (dest / "existing.txt").write_text("hi", encoding="utf-8")

    def unexpected_run_copy(**_kwargs: object) -> None:
        raise AssertionError("run_copy must not run against a non-empty destination")

    monkeypatch.setattr(runner_module, "run_copy", unexpected_run_copy)

    result = runner.invoke(
        app, ["new", "--legacy", "Foo", "--yes", "--path", str(dest)]
    )

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

    result = runner.invoke(
        app, ["new", "--legacy", "Foo", "--yes", "--path", str(dest)]
    )

    assert result.exit_code == 1, result.output
    assert not dest.exists()
    # CF-25.01: the equivalent check on the engine route
    # (`test_new_reports_lock_failure_and_writes_nothing`, below) already
    # existed at the pipeline layer (`test_data_science_pipeline.py`) but
    # never through `CliRunner` on either route.
    assert staging_siblings(dest) == []


def test_new_legacy_keyboard_interrupt_leaves_nothing_behind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CF-25.01: nothing previously exercised Ctrl-C mid-`new` through
    `CliRunner`. `staging.discard_on_failure` already catches
    `BaseException`, not just `Exception` -- this proves that reaches a real
    `KeyboardInterrupt`, not only the ordinary failures every other test in
    this module raises. `CliRunner` converts an uncaught `KeyboardInterrupt`
    to `SystemExit(130)`, matching the existing Ctrl-C-at-a-prompt exit `130`.
    """
    dest = tmp_path / "proj"

    def interrupting_run_copy(**kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(runner_module, "run_copy", interrupting_run_copy)

    result = runner.invoke(
        app, ["new", "--legacy", "Foo", "--yes", "--path", str(dest)]
    )

    assert result.exit_code == 130
    assert not dest.exists()
    assert staging_siblings(dest) == []


def test_new_leaves_a_pre_existing_destination_untouched_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dest = tmp_path / "proj"
    dest.mkdir()  # exists and is empty -- a legitimate --path target

    def failing_run_copy(**_kwargs: object) -> None:
        raise CopierError("simulated render failure")

    monkeypatch.setattr(runner_module, "run_copy", failing_run_copy)

    result = runner.invoke(
        app, ["new", "--legacy", "Foo", "--yes", "--path", str(dest)]
    )

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
            "--legacy",
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


def test_new_with_legacy_is_unchanged(
    recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """`--legacy` still reaches the Copier path exactly as the pre-cutover
    default did -- every Copier-path test above already proves this, but this
    makes it explicit and future-proof.
    """
    result = runner.invoke(
        app, ["new", "--legacy", "Foo", "--yes", "--path", str(tmp_path / "proj")]
    )

    assert result.exit_code == 0, result.output
    assert len(recorder) == 1


def test_new_config_reaches_scaffold_data(
    recorder: list[ScaffoldRequest], _isolated_config: Path, tmp_path: Path
) -> None:
    write_config(
        _isolated_config,
        'author_name = "Config Author"\ngithub_org = "config-org"\n',
    )

    result = runner.invoke(
        app,
        [
            "new",
            "--legacy",
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
    write_config(_isolated_config, 'github_org = "config-org"\n')

    result = runner.invoke(
        app,
        [
            "new",
            "--legacy",
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
    write_config(_isolated_config, "not = [valid toml")

    result = runner.invoke(app, ["new", "--legacy", "X", "--yes"])

    assert result.exit_code == 1
    assert recorder == []
    assert "not valid TOML" in result.output


def test_new_unknown_default_template_names_the_config_path(
    _isolated_config: Path, recorder: list[ScaffoldRequest]
) -> None:
    write_config(_isolated_config, 'default_template = "does-not-exist"\n')

    result = runner.invoke(app, ["new", "--legacy", "X", "--yes"])

    # Rich wraps long lines in CliRunner's fixed-width capture, so compare
    # with newlines collapsed rather than requiring one contiguous substring.
    flattened = result.output.replace("\n", "")

    assert result.exit_code == 1
    assert recorder == []
    assert str(_isolated_config) in flattened
    assert "does-not-exist" in flattened
