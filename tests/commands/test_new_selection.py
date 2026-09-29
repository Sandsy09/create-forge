"""`commands/selection.py` -- archetype/flag selection and engine-native
prompting (#91, ADR 0025), reached through `commands/new.py`'s engine route.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import questionary
from typer.testing import CliRunner

import create_forge.staging as staging_module
from create_forge import pipeline as pipeline_module
from create_forge.cli import app
from create_forge.commands import new as new_module
from create_forge.commands import selection as selection_module
from create_forge.pipeline import GenerationRequest
from create_forge.prompts import PromptAbortedError
from create_forge.runner import ScaffoldRequest
from tests.commands import support

if TYPE_CHECKING:
    from collections.abc import Mapping

runner = CliRunner()


def test_new_archetype_with_legacy_is_rejected(
    recorder: list[ScaffoldRequest],
) -> None:
    """`--archetype` selects an engine archetype (CF-08.02); combined with
    `--legacy`'s Copier path it is contradictory and must not be silently
    ignored.
    """
    result = runner.invoke(
        app, ["new", "--legacy", "Foo", "--yes", "--archetype", "cli"]
    )

    assert result.exit_code == 1, result.output
    assert "--archetype and --legacy are contradictory" in result.output
    assert recorder == []


def test_new_yes_without_archetype_is_rejected(
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
        ],
    )

    assert result.exit_code == 1, result.output
    assert "--yes" in result.output
    assert "requires --archetype" in result.output
    assert "cli" in result.output
    assert "library" in result.output
    assert recorder == []
    assert not dest.exists()


def test_new_unknown_archetype_is_rejected(
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
            *support.ENGINE_ANSWERS,
            "--archetype",
            "nonexistent",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "Unknown archetype 'nonexistent'" in result.output
    assert recorder == []
    assert not dest.exists()


def test_new_prompts_when_archetype_is_omitted(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """Without `--yes` or `--archetype`, selection falls to an interactive
    prompt over the real discovered catalogue (CF-08.02) -- mirroring
    `test_new_interactive_resolves_template_and_answers`'s style of
    monkeypatching the prompt functions themselves rather than driving real
    stdin through questionary. Project-answer and component-option
    collection are likewise faked here (#91, ADR 0025): only archetype
    selection is under test. No registry template is selected at all on this
    path any more, so nothing here mentions `choose_template`.
    """
    monkeypatch.setattr(
        selection_module,
        "ask_project_answers",
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
    monkeypatch.setattr(
        selection_module, "resolve_component_options", lambda *_a, **_kw: {}
    )
    # CF-13.03: the real 0.4 catalogue has capability descriptors, so an
    # interactive run now reaches a capability multi-select; this test is
    # about archetype selection only, so short-circuit it.
    monkeypatch.setattr(selection_module, "choose_components", lambda *_a, **_kw: ())

    seen_archetypes: list[str] = []

    def fake_choose_archetype(archetypes: object) -> object:
        ids = [a.id for a in archetypes]  # type: ignore[attr-defined]
        seen_archetypes.extend(ids)
        return next(a for a in archetypes if a.id == "cli")  # type: ignore[attr-defined]

    monkeypatch.setattr(selection_module, "choose_archetype", fake_choose_archetype)

    dest = tmp_path / "proj"
    result = runner.invoke(app, ["new", "--path", str(dest)])

    assert result.exit_code == 0, result.output
    assert {"library", "cli"} <= set(seen_archetypes)
    assert recorder == []
    assert (dest / "src" / "engine_preview" / "cli.py").exists()


def test_new_aborting_archetype_choice_exits_130(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """Mirrors `test_new_aborting_the_template_choice_exits_130`'s shape for
    the archetype prompt (CF-08.02). Archetype selection now runs before any
    answer is collected (#91, ADR 0025), so the abort fires before
    `ask_project_answers` is ever reached -- nothing needs faking there.
    """

    def _abort(*_args: object, **_kwargs: object) -> object:
        raise PromptAbortedError

    monkeypatch.setattr(selection_module, "choose_archetype", _abort)

    dest = tmp_path / "proj"
    result = runner.invoke(app, ["new", "--path", str(dest)])

    assert result.exit_code == 130, result.output
    assert recorder == []
    assert not dest.exists()


class _Answer:
    """Stands in for questionary's `Question`, returning a canned value."""

    def __init__(self, value: object) -> None:
        self._value = value

    def ask(self) -> object:
        return self._value


def test_new_cli_archetype_asks_no_library_question(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """#91 / ADR 0025's first acceptance criterion, against the real
    installed engine: `cli`'s own discovered descriptor declares no options,
    and the engine path reads no registry data at all, so none of the
    Library-specific vocabulary (`build_backend`, `versioning`,
    `type_checking`, `use_docs`, `github_org`) can appear -- only ProjectSpec's
    own three identity prompts are ever asked.
    """
    seen_messages: list[str] = []

    def fake_text(message: str, **_kwargs: object) -> _Answer:
        seen_messages.append(message)
        if message == "Project name":
            return _Answer("Engine Preview")
        return _Answer("A description")

    def fake_select(message: str, *, choices: object, **_kwargs: object) -> _Answer:
        seen_messages.append(message)
        return _Answer("mit")

    def fake_confirm(message: str, **_kwargs: object) -> _Answer:
        pytest.fail(f"unexpected confirm prompt: {message!r}")

    checkbox_messages: list[str] = []

    def fake_checkbox(message: str, **_kwargs: object) -> _Answer:
        checkbox_messages.append(message)
        return _Answer([])

    monkeypatch.setattr(questionary, "text", fake_text)
    monkeypatch.setattr(questionary, "select", fake_select)
    monkeypatch.setattr(questionary, "confirm", fake_confirm)
    monkeypatch.setattr(questionary, "checkbox", fake_checkbox)

    dest = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "new",
            "--path",
            str(dest),
            "--archetype",
            "cli",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert seen_messages == ["Project name", "Short description", "License"]
    # CF-13.03: `cli` requires no capability or platform, but the catalogue
    # has descriptors of both kinds, so both multi-selects are still offered
    # -- with the engine's own kind vocabulary, never a Library-specific
    # question. The `github` platform shipped at FT-17.02 / ADR 0063.
    assert checkbox_messages == ["Which capabilities?", "Which platforms?"]
    assert recorder == []


def test_new_library_archetype_asks_declared_options_only(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """The counterpart to the `cli` case above: `library`'s own discovered
    descriptor declares exactly `packaging_mode` and `initial_version`, both
    asked directly, and an answered `packaging_mode` reaches
    `component_options` -- inspected on the real resolved `GenerationRequest`
    rather than a render.
    """
    seen_messages: list[str] = []
    captured: dict[str, object] = {}
    real_build = pipeline_module.build_generation_request

    def fake_text(message: str, **_kwargs: object) -> _Answer:
        seen_messages.append(message)
        if message == "Project name":
            return _Answer("Engine Preview")
        if message == "Short description":
            return _Answer("A description")
        return _Answer("0.1.0")  # initial_version's own description

    def fake_select(message: str, *, choices: object, **_kwargs: object) -> _Answer:
        seen_messages.append(message)
        if message == "License":
            return _Answer("mit")
        return _Answer("hatchling-vcs")  # packaging_mode's own description

    def fake_confirm(message: str, **_kwargs: object) -> _Answer:
        pytest.fail(f"unexpected confirm prompt: {message!r}")

    def fake_checkbox(message: str, **_kwargs: object) -> _Answer:
        return _Answer([])

    def spy(answers: Mapping[str, object], **kwargs: object) -> GenerationRequest:
        captured.update(kwargs)
        return real_build(answers, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(questionary, "text", fake_text)
    monkeypatch.setattr(questionary, "select", fake_select)
    monkeypatch.setattr(questionary, "confirm", fake_confirm)
    monkeypatch.setattr(questionary, "checkbox", fake_checkbox)
    monkeypatch.setattr(pipeline_module, "build_generation_request", spy)

    dest = tmp_path / "proj"
    result = runner.invoke(
        app,
        [
            "new",
            "--path",
            str(dest),
            "--archetype",
            "library",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    # The first three messages are create-forge's own, stable text; the last
    # two are `library`'s own engine-owned option descriptions -- matched by
    # prefix rather than full equality, since their exact wording is not this
    # repository's to pin down.
    assert seen_messages[:3] == ["Project name", "Short description", "License"]
    assert seen_messages[3].startswith("How the package is built and versioned.")
    assert seen_messages[4].startswith("Initial package version.")
    assert captured["component_options"] == {
        "library": {"packaging_mode": "hatchling-vcs", "initial_version": "0.1.0"}
    }
    assert recorder == []


def test_new_never_loads_the_registry(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """#91 / ADR 0025: the engine path reads no registry data at all -- a
    broken or absent `templates.toml` must not affect it.
    """

    def fail_load_registry() -> None:
        raise AssertionError("the engine path must not load the registry")

    monkeypatch.setattr(new_module, "load_registry", fail_load_registry)

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
            *support.ENGINE_ANSWERS,
            "--archetype",
            "cli",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (dest / "src" / "engine_preview" / "cli.py").exists()
    assert recorder == []


def test_new_interactive_asks_what_are_you_building_once(
    monkeypatch: pytest.MonkeyPatch, recorder: list[ScaffoldRequest], tmp_path: Path
) -> None:
    """#91 / ADR 0025: since the engine path no longer selects a Copier
    template at all, the old double "What are you building?" prompt (once
    for the registry template, once for the archetype) collapses to one.
    """
    seen_prompts: list[str] = []

    def fake_select(message: str, *, choices: object, **_kwargs: object) -> _Answer:
        seen_prompts.append(message)
        if message == "What are you building?":
            chosen = next(c for c in choices if c.value.id == "cli")  # type: ignore[attr-defined]
            return _Answer(chosen.value)
        if message == "License":
            return _Answer("mit")
        raise AssertionError(f"unexpected select prompt: {message!r}")

    def fake_text(message: str, **_kwargs: object) -> _Answer:
        if message == "Project name":
            return _Answer("Engine Preview")
        if message == "Short description":
            return _Answer("A description")
        raise AssertionError(f"unexpected text prompt: {message!r}")

    def fake_confirm(message: str, **_kwargs: object) -> _Answer:
        pytest.fail(f"unexpected confirm prompt: {message!r}")

    def fake_checkbox(message: str, **_kwargs: object) -> _Answer:
        seen_prompts.append(message)
        return _Answer([])

    monkeypatch.setattr(questionary, "select", fake_select)
    monkeypatch.setattr(questionary, "text", fake_text)
    monkeypatch.setattr(questionary, "confirm", fake_confirm)
    monkeypatch.setattr(questionary, "checkbox", fake_checkbox)

    dest = tmp_path / "proj"
    result = runner.invoke(app, ["new", "--path", str(dest), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert seen_prompts.count("What are you building?") == 1
    assert recorder == []


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--template", "library"),
        ("--template-url", "https://example.com/x"),
        ("--ref", "v1.0.0"),
    ],
)
def test_new_rejects_copier_only_flags_without_legacy(
    flag: str, value: str, recorder: list[ScaffoldRequest]
) -> None:
    """ADR 0040 (CF-18.01): `--template`/`--template-url`/`--ref` select a
    Copier template, source, or ref -- meaningless on the default engine
    path, which reads no registry data and clones no template. Silently
    ignoring them would leave a user believing one was in force; reject
    instead, requiring `--legacy` to use them at all.
    """
    result = runner.invoke(
        app,
        ["new", "Foo", "--yes", "--archetype", "cli", flag, value],
    )

    assert result.exit_code == 1, result.output
    assert "--legacy" in result.output
    assert recorder == []
