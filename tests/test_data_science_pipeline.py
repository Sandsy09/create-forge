"""CF-13.05 / ADR 0030: the Data Science composition through the shared
`--engine-preview` pipeline.

CF-13.01-13.04 built the discovery-driven preview path; this module proves the
released Data Science archetype and its two capabilities actually traverse it
-- construction, validation, render, dry-run, staging, lock, and finalisation
-- through the *same* `pipeline.build_generation_request` /
`finalise_generation_request` as `library` and `cli`, and that every failure
mode leaves nothing behind.

Exercises the real installed `forge_template` engine (the `engine` extra,
present under `uv sync --all-extras`), like `tests/test_component_selection.py`
and `tests/test_pipeline.py`. The `data-science` / `jupyter` /
`scientific-python` ids that appear are fixture data feeding the real engine,
never selection logic -- `tests/test_archetype_parity.py`'s widened AST guard
enforces the shipped-module half of that rule. Assertions are derived from the
engine's own `plan.files` owners and target list wherever possible; the two
named path anchors exist only to prove each capability is contributing, not to
restate a file manifest this repository does not own.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import questionary
from forge_template import EngineInfo
from typer.testing import CliRunner

import create_forge.pipeline as pipeline_module
import create_forge.staging as staging_module
from create_forge import engine as engine_module
from create_forge.cli import app
from create_forge.config import UserConfig, config_path
from create_forge.pipeline import build_generation_request
from create_forge.spec import SelectionKind, SelectionRequest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from forge_template import RenderedProject

runner = CliRunner()

# The full Data Science composition: the archetype, its hard requirement, and
# the independently-optional capability. Non-interactive selection passes each
# as a `--capability`; the in-memory helpers pass the same tuple.
_ARCHETYPE = "data-science"
_REQUIRED_CAPABILITY = "jupyter"
_OPTIONAL_CAPABILITY = "scientific-python"
_FULL_CAPABILITIES = (_REQUIRED_CAPABILITY, _OPTIONAL_CAPABILITY)

_YES_DATA = [
    "--data",
    "license=mit",
    "--data",
    "project_description=x",
    "--yes",
]

_ANSWERS = {
    "project_name": "Risk Models",
    "project_description": "x",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
}


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same isolation `tests/test_component_selection.py` uses: no real user
    config or `FORGE_*` environment leaks into these invocations.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    for name in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{name.upper()}", raising=False)
    assert config_path()


def _capability_flags(capabilities: Sequence[str]) -> list[str]:
    return [arg for capability in capabilities for arg in ("--capability", capability)]


def _owner_id(owner: object) -> str | None:
    """A `PlannedFile.owner` is `FoundationOwner(kind)` or
    `ComponentOwner(kind, id)`; only the latter names a component.
    """
    return getattr(owner, "id", None)


def _render(capabilities: Sequence[str]) -> RenderedProject:
    """A real in-memory render of the composition -- no filesystem effect."""
    request = build_generation_request(
        dict(_ANSWERS),
        selection=SelectionRequest.of(
            archetype=_ARCHETYPE,
            capabilities=tuple(capabilities),
            capabilities_explicit=True,
        ),
    )
    return request.rendered


def _fake_lock(staging_dir: Path) -> None:
    (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")


def _staging_siblings(dest: Path) -> list[Path]:
    return [p for p in dest.parent.iterdir() if p.name.startswith(".create-forge-")]


# --------------------------------------------------------------------------
# a valid composition through the shared pipeline
# --------------------------------------------------------------------------


def test_every_selected_component_contributes_to_the_render() -> None:
    """Derived: the component owners on `plan.files` are exactly the selected
    ids. This is what proves `scientific-python` reaches the render rather
    than merely sitting in the spec -- an optional capability that owns no
    file would pass a spec-only check.
    """
    rendered = _render(_FULL_CAPABILITIES)

    component_owners = {
        _owner_id(file.owner)
        for file in rendered.plan.files
        if _owner_id(file.owner) is not None
    }
    assert component_owners == {_ARCHETYPE, *_FULL_CAPABILITIES}

    # composition-tier order, archetype before its capabilities
    assert rendered.plan.component_order[0] == _ARCHETYPE
    assert set(rendered.plan.component_order) == {_ARCHETYPE, *_FULL_CAPABILITIES}

    # plan and render agree, exactly and in order
    assert [f.target for f in rendered.plan.files] == [f.target for f in rendered.files]

    # one named anchor per capability, so a silent "owns nothing" regression
    # in the engine fails here rather than passing the set check above
    by_owner: dict[str | None, set[str]] = {}
    for file in rendered.plan.files:
        by_owner.setdefault(_owner_id(file.owner), set()).add(file.target)
    assert any("notebook" in t for t in by_owner[_REQUIRED_CAPABILITY])
    assert any("test" in t for t in by_owner[_OPTIONAL_CAPABILITY])


def test_the_optional_capability_changes_the_render() -> None:
    """The difference between the two renders is exactly the set of targets
    `scientific-python` owns -- nothing the archetype or Jupyter contributes
    moves when the optional capability is added.
    """
    without = {f.target for f in _render((_REQUIRED_CAPABILITY,)).files}
    full_render = _render(_FULL_CAPABILITIES)
    with_optional = {f.target for f in full_render.files}

    optional_targets = {
        f.target
        for f in full_render.plan.files
        if _owner_id(f.owner) == _OPTIONAL_CAPABILITY
    }
    assert optional_targets
    assert with_optional - without == optional_targets
    assert without - with_optional == set()


def test_selected_capabilities_round_trip_into_the_projectspec() -> None:
    """A real engine round-trip asserting `spec.components` -- the gap the one
    existing capability-passing pipeline test leaves open by stubbing the
    engine with ids the 0.4 catalogue does not contain.
    """
    request = build_generation_request(
        dict(_ANSWERS),
        selection=SelectionRequest.of(
            archetype=_ARCHETYPE,
            capabilities=_FULL_CAPABILITIES,
            capabilities_explicit=True,
        ),
    )
    assert request.spec.components.archetype == _ARCHETYPE
    assert tuple(request.spec.components.capabilities) == _FULL_CAPABILITIES
    assert tuple(request.spec.components.platforms) == ()


def test_a_full_composition_stages_locks_and_finalises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The non-interactive path all the way to disk: every planned target is
    present under `dst`, the client-finalised lock alongside it, no staging
    directory survives, and no `_tasks` artefact (`.git`/`.venv`) is created.
    """
    monkeypatch.setattr(staging_module, "create_uv_lock", _fake_lock)
    dest = tmp_path / "risk-models"

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(dest),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
            *_capability_flags(_FULL_CAPABILITIES),
        ],
    )

    assert result.exit_code == 0, result.output

    expected = {f.target for f in _render(_FULL_CAPABILITIES).plan.files}
    on_disk = {
        p.relative_to(dest).as_posix()
        for p in dest.rglob("*")
        if p.is_file() and p.name != "uv.lock"
    }
    assert on_disk == expected
    assert (dest / "uv.lock").is_file()
    assert _staging_siblings(dest) == []
    assert not (dest / ".git").exists()
    assert not (dest / ".venv").exists()


# --------------------------------------------------------------------------
# failures leave no partial project
# --------------------------------------------------------------------------


@pytest.mark.parametrize("capability_args", [[], ["--no-capabilities"]])
def test_a_missing_required_capability_writes_nothing(
    capability_args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both the absent-flag and the explicit-empty forms: create-forge adds
    nothing to the selection, the engine rejects it, and the client's flag
    hint points at the fix -- all before any destination effect.
    """
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda _root: pytest.fail("a rejected selection must not reach staging"),
    )
    dest = tmp_path / "p"

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(dest),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
            *capability_args,
        ],
    )

    assert result.exit_code == 1, result.output
    normalised = " ".join(result.output.split())
    assert f"requires selected component(s): {_REQUIRED_CAPABILITY}" in normalised
    assert f"Add --capability {_REQUIRED_CAPABILITY}." in normalised
    assert not dest.exists()


def test_an_undeclared_component_option_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A `--component-option` for a selected owner that does not declare that
    name is the engine's verdict, surfaced at exit 1 with nothing written --
    the Data Science components declare no options at all.
    """
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda _root: pytest.fail("an invalid option must not reach staging"),
    )
    dest = tmp_path / "p"

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(dest),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
            *_capability_flags((_REQUIRED_CAPABILITY,)),
            "--component-option",
            f"{_REQUIRED_CAPABILITY}.kernel=python3",
        ],
    )

    assert result.exit_code == 1, result.output
    normalised = " ".join(result.output.split())
    assert "unknown option" in normalised
    assert not dest.exists()


def test_an_incompatible_engine_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed engine outside `compat.SUPPORTED_ENGINE_RANGE` is rejected
    at exit 3 before discovery returns -- the fast counterpart to the e2e
    suite's real out-of-range install.
    """
    monkeypatch.setattr(
        engine_module,
        "get_engine_info",
        lambda: EngineInfo(
            package_version="9.0.0",
            projectspec_protocols=(99,),
            component_manifest_protocols=(1,),
        ),
    )
    dest = tmp_path / "p"

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(dest),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
            *_capability_flags(_FULL_CAPABILITIES),
        ],
    )

    assert result.exit_code == 3, result.output
    assert not dest.exists()


def test_a_non_empty_destination_is_rejected_before_the_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0015: the destination conflict is checked before the engine is
    imported -- proven here by making the engine explode if it is reached.
    """
    dest = tmp_path / "p"
    dest.mkdir()
    (dest / "existing.txt").write_text("hi", encoding="utf-8")

    monkeypatch.setattr(
        engine_module,
        "get_engine_info",
        lambda: (_ for _ in ()).throw(AssertionError("engine must not be reached")),
    )

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(dest),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
            *_capability_flags(_FULL_CAPABILITIES),
        ],
    )

    assert result.exit_code == 1, result.output
    assert "already exists and is not empty" in " ".join(result.output.split())
    assert (dest / "existing.txt").read_text(encoding="utf-8") == "hi"


def test_a_lock_failure_leaves_no_partial_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The render succeeds, the lock does not: `staged()` removes the staging
    tree and `dst` is left exactly as it was found -- absent.
    """

    def failing_lock(_staging_dir: Path) -> None:
        raise staging_module.StagingError("uv lock failed with exit status 2")

    monkeypatch.setattr(staging_module, "create_uv_lock", failing_lock)
    dest = tmp_path / "risk-models"

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(dest),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
            *_capability_flags(_FULL_CAPABILITIES),
        ],
    )

    assert result.exit_code == 1, result.output
    assert not dest.exists()
    assert _staging_siblings(dest) == []


# --------------------------------------------------------------------------
# dry run
# --------------------------------------------------------------------------


def test_dry_run_lists_every_planned_target_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--dry-run` prints exactly the set of targets a real render of the same
    selection produces, and touches nothing -- derived from the engine's own
    manifest so it cannot drift from it.
    """
    monkeypatch.setattr(
        staging_module,
        "create_uv_lock",
        lambda _root: pytest.fail("dry-run must not create a lockfile"),
    )
    dest = tmp_path / "risk-models"

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(dest),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
            *_capability_flags(_FULL_CAPABILITIES),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    normalised = " ".join(result.output.split())
    targets = [f.target for f in _render(_FULL_CAPABILITIES).files]
    for target in targets:
        assert target in normalised
    assert normalised.count("would write") == len(targets)
    assert "nothing written" in normalised
    assert not dest.exists()


# --------------------------------------------------------------------------
# interactive parity
# --------------------------------------------------------------------------


class _Reply:
    def __init__(self, value: object) -> None:
        self._value = value

    def ask(self) -> object:
        return self._value


def test_interactive_selection_pre_locks_the_required_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The capability multi-select offers both, with the required one locked;
    ticking the optional one reaches the same `SelectionRequest` the
    non-interactive `--capability` pair produces.
    """
    captured: dict[str, object] = {}

    class _StopBeforeEngineError(Exception):
        pass

    def spy(_answers: object, **kwargs: object) -> None:
        captured.update(kwargs)
        raise _StopBeforeEngineError

    monkeypatch.setattr(pipeline_module, "build_generation_request", spy)

    offered_messages: list[str] = []
    offered_choices: list[object] = []

    def fake_checkbox(
        message: str, *, choices: Sequence[object] = (), **_kw: object
    ) -> _Reply:
        offered_messages.append(message)
        offered_choices.extend(choices)
        return _Reply([_OPTIONAL_CAPABILITY])

    def fake_text(message: str, **_kw: object) -> _Reply:
        return _Reply("Risk Models" if message == "Project name" else "d")

    def fake_select(_message: str, **_kw: object) -> _Reply:
        return _Reply("mit")

    monkeypatch.setattr(questionary, "checkbox", fake_checkbox)
    monkeypatch.setattr(questionary, "text", fake_text)
    monkeypatch.setattr(questionary, "select", fake_select)

    runner.invoke(
        app,
        [
            "new",
            "--path",
            str(tmp_path / "p"),
            "--engine-preview",
            "--archetype",
            _ARCHETYPE,
        ],
    )

    assert offered_messages == ["Which capabilities?"]
    choice_values = {getattr(c, "value", None) for c in offered_choices}
    assert choice_values == set(_FULL_CAPABILITIES)
    locked = {
        getattr(c, "value", None)
        for c in offered_choices
        if getattr(c, "disabled", None)
    }
    assert locked == {_REQUIRED_CAPABILITY}

    selection = captured["selection"]
    assert isinstance(selection, SelectionRequest)
    assert selection.archetype == _ARCHETYPE
    assert set(selection.capabilities) == set(_FULL_CAPABILITIES)
    assert SelectionKind.CAPABILITIES in selection.explicit
