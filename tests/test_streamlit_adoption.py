"""CF-21.01 / ADR 0050: the released Streamlit provider through the generic
selection contract (CF-ROADMAP-02-AC-02).

Proves an interactive and a non-interactive `create-forge new` both select the
`0.6.0` provider's `streamlit` archetype through the same discovery-driven
path every other archetype takes -- reaching staging and finalisation intact.
The `streamlit` id that appears is fixture data feeding the real engine, never
selection logic: `tests/test_archetype_parity.py`'s guards enforce the
shipped-module half of that rule, and installed-console generation, lock
restoration and the bounded smoke belong to CF-21.02.

Exercises the real installed `forge_template` engine, like
`tests/test_data_science_pipeline.py`. Assertions are derived from the engine's
own `plan.files` rather than restating a file manifest this repository does not
own (CF-ROADMAP-02-EX-01).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import create_forge.cli as cli_module
import create_forge.lifecycle as lifecycle_module
import create_forge.staging as staging_module
from create_forge.cli import app
from create_forge.config import UserConfig, config_path
from create_forge.pipeline import build_generation_request
from create_forge.spec import SelectionRequest

runner = CliRunner()

_ARCHETYPE = "streamlit"

_ANSWERS = {
    "project_name": "Insight Board",
    "project_description": "x",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
}


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same isolation `tests/test_data_science_pipeline.py` uses: no real user
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
    """The engine's own planned targets for a bare Streamlit selection."""
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


def test_a_non_interactive_run_selects_streamlit_generically(tmp_path: Path) -> None:
    """`--archetype streamlit --yes` resolves through discovery and generates
    the project, with no Streamlit-specific flag, prompt or branch.
    """
    dest = tmp_path / "insight-board"

    result = runner.invoke(
        app,
        [
            "new",
            "Insight Board",
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


def test_an_interactive_run_offers_and_selects_streamlit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The interactive archetype prompt is built from discovery, so the
    `0.6.0` provider's archetype is offered beside the others with no prompt
    change, and choosing it generates the project.
    """
    monkeypatch.setattr(
        cli_module,
        "ask_project_answers",
        lambda *_a, **_kw: {**_ANSWERS, "github_org": "test-org"},
    )
    # This is about archetype selection; skip the capability multi-select the
    # real catalogue would otherwise reach.
    monkeypatch.setattr(cli_module, "choose_components", lambda *_a, **_kw: ())

    offered: list[str] = []

    def choose(archetypes: object) -> object:
        offered.extend(a.id for a in archetypes)  # type: ignore[attr-defined]
        return next(a for a in archetypes if a.id == _ARCHETYPE)  # type: ignore[attr-defined]

    monkeypatch.setattr(cli_module, "choose_archetype", choose)

    dest = tmp_path / "insight-board"
    result = runner.invoke(app, ["new", "--path", str(dest)])

    assert result.exit_code == 0, result.output
    assert _ARCHETYPE in offered
    assert len(offered) > 1, "streamlit must be offered beside the other archetypes"
    _assert_finalised(dest)
