"""CF-29.01 / ADR 0061: the released batch provider through the generic
selection contract (CF-ROADMAP-02-AC-02).

Proves an interactive and a non-interactive `create-forge new` both select the
`0.7.0` provider's `batch` archetype through the same discovery-driven path
every other archetype takes -- reaching staging and finalisation intact. The
`batch` id that appears is fixture data feeding the real engine, never
selection logic: `tests/test_archetype_parity.py`'s guards enforce the
shipped-module half of that rule, and installed-console generation, lock
restoration and the bounded example job belong to CF-29.02.

Exercises the real installed `forge_template` engine, like
`tests/test_streamlit_adoption.py`. Assertions are derived from the engine's
own `plan.files` rather than restating a file manifest this repository does not
own (CF-ROADMAP-02-EX-01).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import questionary
from typer.testing import CliRunner

import create_forge.lifecycle as lifecycle_module
import create_forge.staging as staging_module
from create_forge import engine
from create_forge.cli import app
from create_forge.config import UserConfig, config_path
from create_forge.pipeline import build_generation_request
from create_forge.spec import SelectionRequest

runner = CliRunner()

_ARCHETYPE = "batch"

_ANSWERS = {
    "project_name": "Nightly Job",
    "project_description": "x",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
}


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same isolation `tests/test_streamlit_adoption.py` uses: no real user
    config or `FORGE_*` environment leaks into these invocations, and the
    lock and post-rename Git/hook lifecycle are faked -- this is about
    selection reaching finalisation, not `uv`, `git` or `pre-commit`, which
    `tests/test_lifecycle.py` and the e2e suite cover with real subprocesses.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    for name in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{name.upper()}", raising=False)
    assert config_path()
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda staging_dir: (staging_dir / "uv.lock").write_text(
            "version = 1\n", encoding="utf-8"
        ),
    )
    monkeypatch.setattr(lifecycle_module, "finalise_project", lambda dst: ())


def _planned_targets() -> set[str]:
    """The engine's own planned targets for a bare batch selection."""
    request = build_generation_request(
        dict(_ANSWERS), selection=SelectionRequest.of(archetype=_ARCHETYPE)
    )
    return {f.target for f in request.rendered.plan.files}


def _assert_finalised(dest: Path) -> None:
    """Every planned target is on disk beside the client-finalised lock and
    the committed generation metadata, with no staging directory left behind.
    """
    on_disk = {
        p.relative_to(dest).as_posix()
        for p in dest.rglob("*")
        if p.is_file()
        and p.name != "uv.lock"
        and p.relative_to(dest).as_posix() != ".forge/generation.json"
    }
    assert on_disk == _planned_targets()
    assert (dest / "uv.lock").is_file()
    assert (dest / ".forge" / "generation.json").is_file()
    assert [
        p for p in dest.parent.iterdir() if p.name.startswith(".create-forge-")
    ] == []


def test_a_non_interactive_run_selects_batch_generically(tmp_path: Path) -> None:
    """`--archetype batch --yes` resolves through discovery and generates the
    project, with no batch-specific flag, prompt or branch.
    """
    dest = tmp_path / "nightly-job"

    result = runner.invoke(
        app,
        [
            "new",
            "Nightly Job",
            "--path",
            str(dest),
            "--data",
            "license=mit",
            "--data",
            "project_description=x",
            "--yes",
            "--archetype",
            _ARCHETYPE,
        ],
    )

    assert result.exit_code == 0, result.output
    _assert_finalised(dest)


class _Answer:
    """Stands in for questionary's `Question`, returning a canned value --
    the same pattern `tests/test_streamlit_adoption.py` uses. Patches
    `questionary` itself rather than `commands.selection`'s re-exported
    names (CF-25.03's coupling rule), so this proves discovery offers `batch`
    at the real prompt layer, not just that a mocked function was called.
    """

    def __init__(self, value: object) -> None:
        self._value = value

    def ask(self) -> object:
        return self._value


def test_an_interactive_run_offers_and_selects_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The interactive archetype prompt is built from discovery, so the
    `0.7.0` provider's archetype is offered beside the others with no prompt
    change, in discovery order, and choosing it generates the project.

    Discovery order is provider-owned and the generic contract makes no
    ordering promise (ADR 0061): `batch` sorts first, so the prompt's cursor
    now starts on it. Asserting the offered ids equal the discovered
    archetypes, in order, pins that consequence without naming `batch` as a
    default anywhere in production code.
    """
    offered: list[str] = []

    def fake_select(message: str, *, choices: object, **_kw: object) -> _Answer:
        if message == "What are you building?":
            offered.extend(c.value.id for c in choices)  # type: ignore[attr-defined]
            chosen = next(c for c in choices if c.value.id == _ARCHETYPE)  # type: ignore[attr-defined]
            return _Answer(chosen.value)
        if message == "License":
            return _Answer("mit")
        raise AssertionError(f"unexpected select prompt: {message!r}")

    def fake_text(message: str, **_kw: object) -> _Answer:
        if message == "Project name":
            return _Answer(_ANSWERS["project_name"])
        if message == "Short description":
            return _Answer(_ANSWERS["project_description"])
        raise AssertionError(f"unexpected text prompt: {message!r}")

    # This is about archetype selection; skip the capability/platform
    # multi-select the real catalogue would otherwise reach.
    monkeypatch.setattr(questionary, "checkbox", lambda *_a, **_kw: _Answer([]))
    monkeypatch.setattr(questionary, "select", fake_select)
    monkeypatch.setattr(questionary, "text", fake_text)

    dest = tmp_path / "nightly-job"
    result = runner.invoke(app, ["new", "--path", str(dest)])

    assert result.exit_code == 0, result.output
    assert _ARCHETYPE in offered
    assert len(offered) > 1, "batch must be offered beside the other archetypes"
    assert offered == [d.id for d in engine.discover() if d.kind == "archetype"]
    _assert_finalised(dest)


def test_an_undeclared_component_option_on_batch_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`batch` declares no options, so a `--component-option` naming one is
    the engine's verdict through the existing generic path -- exit 1, nothing
    staged, nothing written.
    """
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda _root: pytest.fail("an invalid option must not reach staging"),
    )
    dest = tmp_path / "nightly-job"

    result = runner.invoke(
        app,
        [
            "new",
            "Nightly Job",
            "--path",
            str(dest),
            "--data",
            "license=mit",
            "--data",
            "project_description=x",
            "--yes",
            "--archetype",
            _ARCHETYPE,
            "--component-option",
            f"{_ARCHETYPE}.schedule=daily",
        ],
    )

    assert result.exit_code == 1, result.output
    assert not dest.exists()
    assert [
        p for p in dest.parent.iterdir() if p.name.startswith(".create-forge-")
    ] == []
