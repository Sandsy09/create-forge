"""CF-13.03 / ADR 0028: discovery-driven capability and platform selection.

The flag surface, the absent-versus-explicit encoding, required pre-locking,
deterministic prompt order, and the client-versus-engine validation split
defined by the canonical
[component selection contract](../docs/component-selection.md).

Exercises the real installed `forge_template` engine (the `engine` extra,
present under `uv sync --all-extras`), like `tests/test_pipeline.py`. Shapes
the 0.4 catalogue cannot produce -- an archetype that requires every
descriptor of a kind -- use a synthetic `Catalogue` built from the real
public models. No production component id is asserted as selection logic; the
few that appear are test fixtures feeding the real engine, exactly as
`tests/test_pipeline.py` already does.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import questionary
from forge_template import ComponentDescriptor, ComponentOption, ComponentRelation
from typer.testing import CliRunner

import create_forge.pipeline as pipeline_module
import create_forge.staging as staging_module
from create_forge import engine as engine_module
from create_forge.cli import app
from create_forge.config import UserConfig, config_path
from create_forge.pipeline import Catalogue
from create_forge.prompts import PromptAbortedError, choose_components
from create_forge.spec import SelectionKind, SelectionRequest

if TYPE_CHECKING:
    from collections.abc import Mapping

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same isolation `tests/test_cli.py` uses: no real user config or
    `FORGE_*` environment leaks into these invocations.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    for name in UserConfig.model_fields:
        monkeypatch.delenv(f"FORGE_{name.upper()}", raising=False)
    assert config_path()  # touch it so a misconfiguration fails loudly here


# --------------------------------------------------------------------------
# synthetic catalogue helpers
# --------------------------------------------------------------------------


def _descriptor(
    component_id: str,
    kind: str,
    *,
    requires: tuple[ComponentRelation, ...] = (),
    options: tuple[ComponentOption, ...] = (),
) -> ComponentDescriptor:
    return ComponentDescriptor(
        id=component_id,
        name=component_id.replace("-", " ").title(),
        description=f"The {component_id} {kind}.",
        kind=kind,  # type: ignore[arg-type]
        version="1.0.0",
        projectspec_protocols=(1,),
        requires_python=">=3.11",
        requires=requires,
        conflicts=(),
        options=options,
    )


def _option(name: str, option_type: str = "string") -> ComponentOption:
    return ComponentOption(
        name=name,
        type=option_type,  # type: ignore[arg-type]
        required=False,
        default=None,
        choices=(),
        description=f"The {name} option.",
        format=None,
    )


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------


def test_catalogue_groups_descriptors_by_kind() -> None:
    catalogue = Catalogue(
        (
            _descriptor("arch-a", "archetype"),
            _descriptor("cap-a", "capability"),
            _descriptor("cap-b", "capability"),
            _descriptor("plat-a", "platform"),
        )
    )

    assert [d.id for d in catalogue.archetypes] == ["arch-a"]
    assert [d.id for d in catalogue.of_kind(SelectionKind.CAPABILITIES)] == [
        "cap-a",
        "cap-b",
    ]
    assert [d.id for d in catalogue.of_kind(SelectionKind.PLATFORMS)] == ["plat-a"]


def test_catalogue_kind_of_resolves_a_discovered_id_and_none_for_unknown() -> None:
    catalogue = Catalogue(
        (_descriptor("arch-a", "archetype"), _descriptor("cap-a", "capability"))
    )

    assert catalogue.kind_of("arch-a") is SelectionKind.ARCHETYPE
    assert catalogue.kind_of("cap-a") is SelectionKind.CAPABILITIES
    assert catalogue.kind_of("nope") is None


def test_catalogue_required_ids_is_direct_and_kind_filtered() -> None:
    """No transitive closure, and each requirement filtered to the asked kind
    by resolving the relation id back through the catalogue.
    """
    catalogue = Catalogue(
        (
            _descriptor(
                "arch-a",
                "archetype",
                requires=(
                    ComponentRelation(id="cap-a", version=">=1"),
                    ComponentRelation(id="plat-a", version=">=1"),
                    ComponentRelation(id="ghost", version=">=1"),
                ),
            ),
            _descriptor(
                "cap-a",
                "capability",
                requires=(ComponentRelation(id="cap-b", version=">=1"),),
            ),
            _descriptor("cap-b", "capability"),
            _descriptor("plat-a", "platform"),
        )
    )

    assert catalogue.required_ids("arch-a", SelectionKind.CAPABILITIES) == ("cap-a",)
    assert catalogue.required_ids("arch-a", SelectionKind.PLATFORMS) == ("plat-a",)
    # cap-b is cap-a's requirement, not arch-a's -- no closure.
    assert catalogue.required_ids("arch-a", SelectionKind.CAPABILITIES) == ("cap-a",)
    # unknown component id -> nothing, the engine rejects it authoritatively.
    assert catalogue.required_ids("ghost", SelectionKind.CAPABILITIES) == ()


# --------------------------------------------------------------------------
# choose_components: required pre-locking, and the toggle-all reinstate
# --------------------------------------------------------------------------


def test_choose_components_locks_and_annotates_a_required_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, list[object]] = {}

    class _Q:
        def ask(self) -> list[str]:
            return ["cap-b"]

    def fake_checkbox(message: str, *, choices: list[object], **_kw: object) -> _Q:
        seen["message"] = [message]
        seen["choices"] = choices
        return _Q()

    monkeypatch.setattr(questionary, "checkbox", fake_checkbox)

    result = choose_components(
        "Which capabilities?",
        [_descriptor("cap-a", "capability"), _descriptor("cap-b", "capability")],
        required=["cap-a"],
        required_by="arch-a",
    )

    assert result == ("cap-a", "cap-b")
    locked = next(c for c in seen["choices"] if c.value == "cap-a")  # type: ignore[attr-defined]
    assert locked.checked is True  # type: ignore[attr-defined]
    assert locked.disabled == "required by arch-a"  # type: ignore[attr-defined]


def test_choose_components_reinstates_a_required_id_cleared_by_toggle_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """questionary's select-all key wipes even a disabled entry; the required
    id must survive it because the user saw it locked.
    """

    class _Empty:
        def ask(self) -> list[str]:
            return []

    monkeypatch.setattr(questionary, "checkbox", lambda *_a, **_kw: _Empty())

    result = choose_components(
        "Which capabilities?",
        [_descriptor("cap-a", "capability"), _descriptor("cap-b", "capability")],
        required=["cap-a"],
        required_by="arch-a",
    )

    assert result == ("cap-a",)


def test_choose_components_empty_result_is_a_legitimate_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Empty:
        def ask(self) -> list[str]:
            return []

    monkeypatch.setattr(questionary, "checkbox", lambda *_a, **_kw: _Empty())

    assert (
        choose_components(
            "Which capabilities?",
            [_descriptor("cap-a", "capability")],
            required_by="arch-a",
        )
        == ()
    )


def test_choose_components_cancellation_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Cancel:
        def ask(self) -> None:
            return None

    monkeypatch.setattr(questionary, "checkbox", lambda *_a, **_kw: _Cancel())

    with pytest.raises(PromptAbortedError):
        choose_components(
            "Which capabilities?",
            [_descriptor("cap-a", "capability")],
            required_by="arch-a",
        )


# --------------------------------------------------------------------------
# CLI: the flag surface
# --------------------------------------------------------------------------

_YES_DATA = [
    "--data",
    "license=mit",
    "--data",
    "project_description=x",
    "--yes",
]


class _StopBeforeEngineError(Exception):
    """Raised by the spy so no real render runs -- the SelectionRequest that
    reached the pipeline is all these cases assert on.
    """


@pytest.fixture
def captured_selection(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    def spy(_answers: Mapping[str, object], **kwargs: object) -> None:
        captured.update(kwargs)
        raise _StopBeforeEngineError

    monkeypatch.setattr(pipeline_module, "build_generation_request", spy)
    return captured


def _selection(captured: dict[str, object]) -> SelectionRequest:
    value = captured["selection"]
    assert isinstance(value, SelectionRequest)
    return value


@pytest.mark.parametrize(
    "flag",
    ["--capability", "--platform"],
)
def test_selection_flag_without_engine_preview_is_rejected(flag: str) -> None:
    result = runner.invoke(app, ["new", "X", *_YES_DATA, flag, "jupyter"])

    assert result.exit_code == 1, result.output
    assert "require --engine-preview" in " ".join(result.output.split())


@pytest.mark.parametrize("flag", ["--no-capabilities", "--no-platforms"])
def test_explicit_none_flag_without_engine_preview_is_rejected(flag: str) -> None:
    result = runner.invoke(app, ["new", "X", *_YES_DATA, flag])

    assert result.exit_code == 1, result.output
    assert "require --engine-preview" in " ".join(result.output.split())


def test_contradictory_capability_flags_are_rejected(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "cli",
            "--capability",
            "jupyter",
            "--no-capabilities",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "contradictory" in result.output
    assert not (tmp_path / "p").exists()


def test_unknown_capability_id_is_rejected_before_any_effect(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "cli",
            "--capability",
            "not-a-real-capability",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "Unknown --capability 'not-a-real-capability'" in result.output
    assert captured_selection == {}
    assert not (tmp_path / "p").exists()


def test_wrong_kind_id_for_a_flag_is_rejected(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "data-science",
            "--capability",
            "library",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "not a capability" in result.output
    assert captured_selection == {}


# --------------------------------------------------------------------------
# CLI: absent versus explicitly empty
# --------------------------------------------------------------------------


def test_yes_without_a_flag_leaves_the_kind_absent(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "cli",
        ],
    )

    selection = _selection(captured_selection)
    assert selection.capabilities == ()
    assert selection.platforms == ()
    assert SelectionKind.CAPABILITIES not in selection.explicit
    assert SelectionKind.PLATFORMS not in selection.explicit


def test_no_capabilities_flag_records_an_explicit_empty_choice(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "cli",
            "--no-capabilities",
        ],
    )

    selection = _selection(captured_selection)
    assert selection.capabilities == ()
    assert SelectionKind.CAPABILITIES in selection.explicit


def test_a_supplied_capability_is_explicit_and_deduplicated(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "data-science",
            "--capability",
            "jupyter",
            "--capability",
            "jupyter",
        ],
    )

    selection = _selection(captured_selection)
    assert selection.capabilities == ("jupyter",)
    assert SelectionKind.CAPABILITIES in selection.explicit


def test_zero_platform_descriptors_are_never_prompted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    captured_selection: dict[str, object],
) -> None:
    """The real 0.4 catalogue ships no platform component -- an interactive
    run must skip that multi-select entirely, not offer an empty one.
    """

    def fail(*_a: object, **_kw: object) -> object:
        raise AssertionError("no checkbox should be shown for a zero-descriptor kind")

    monkeypatch.setattr(questionary, "checkbox", fail)
    # answer the archetype's own identity prompts non-interactively
    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "data-science",
            "--capability",
            "jupyter",
        ],
    )

    assert result.exit_code != 0  # _StopBeforeEngineError
    selection = _selection(captured_selection)
    assert selection.platforms == ()
    assert SelectionKind.PLATFORMS not in selection.explicit


# --------------------------------------------------------------------------
# CLI: an archetype that requires every descriptor of a kind (synthetic)
# --------------------------------------------------------------------------


def _install_synthetic_catalogue(
    monkeypatch: pytest.MonkeyPatch, descriptors: tuple[ComponentDescriptor, ...]
) -> None:
    monkeypatch.setattr(engine_module, "discover", lambda: descriptors)


def test_a_kind_with_only_required_descriptors_is_not_prompted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    captured_selection: dict[str, object],
) -> None:
    descriptors = (
        _descriptor(
            "arch-x",
            "archetype",
            requires=(ComponentRelation(id="cap-only", version=">=1"),),
        ),
        _descriptor("cap-only", "capability"),
    )
    _install_synthetic_catalogue(monkeypatch, descriptors)

    def fail(*_a: object, **_kw: object) -> object:
        raise AssertionError("nothing selectable -> no prompt")

    monkeypatch.setattr(questionary, "checkbox", fail)

    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "arch-x",
        ],
    )

    assert result.exit_code != 0  # _StopBeforeEngineError
    selection = _selection(captured_selection)
    assert selection.capabilities == ("cap-only",)
    assert SelectionKind.CAPABILITIES not in selection.explicit


# --------------------------------------------------------------------------
# CLI: prompt order, the missing-requirement hint, single discovery
# --------------------------------------------------------------------------


class _Reply:
    def __init__(self, value: object) -> None:
        self._value = value

    def ask(self) -> object:
        return self._value


def test_all_selection_precedes_all_answer_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    captured_selection: dict[str, object],
) -> None:
    order: list[str] = []

    def fake_checkbox(message: str, **_kw: object) -> _Reply:
        order.append(message)
        return _Reply([])

    def fake_text(message: str, **_kw: object) -> _Reply:
        order.append(message)
        return _Reply("Engine Preview" if message == "Project name" else "d")

    def fake_select(message: str, **_kw: object) -> _Reply:
        order.append(message)
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
            "data-science",
        ],
    )

    assert order[0] == "Which capabilities?"
    assert order[1:4] == ["Project name", "Short description", "License"]
    assert "selection" in captured_selection


def test_missing_hard_requirement_under_yes_prints_the_flag_hint(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "data-science",
        ],
    )

    assert result.exit_code == 1, result.output
    normalised = " ".join(result.output.split())
    assert "requires selected component(s): jupyter" in normalised
    assert "Add --capability jupyter." in normalised
    assert not (tmp_path / "p").exists()


def test_engine_discovery_runs_exactly_once_per_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_discover = engine_module.discover
    calls = 0

    def counting_discover() -> tuple[ComponentDescriptor, ...]:
        nonlocal calls
        calls += 1
        return real_discover()

    monkeypatch.setattr(engine_module, "discover", counting_discover)

    def fake_lock(staging_dir: Path) -> None:
        (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setattr(staging_module, "create_uv_lock", fake_lock)

    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "data-science",
            "--capability",
            "jupyter",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == 1


def test_library_and_cli_archetypes_need_no_new_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0027 compatibility clause: the shipped archetypes still generate
    from `--engine-preview --archetype <id> --yes` with no capability flag.
    """
    monkeypatch.setattr(questionary, "checkbox", lambda *_a, **_kw: _Reply([]))

    def fake_lock(staging_dir: Path) -> None:
        (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setattr(staging_module, "create_uv_lock", fake_lock)

    for archetype in ("library", "cli"):
        result = runner.invoke(
            app,
            [
                "new",
                "Thing",
                "--path",
                str(tmp_path / archetype),
                *_YES_DATA,
                "--engine-preview",
                "--archetype",
                archetype,
            ],
        )
        assert result.exit_code == 0, result.output


# --------------------------------------------------------------------------
# CLI: --component-option (CF-13.04, ADR 0029)
# --------------------------------------------------------------------------


def test_component_option_without_engine_preview_is_rejected() -> None:
    result = runner.invoke(app, ["new", "X", *_YES_DATA, "--component-option", "a.b=c"])

    assert result.exit_code == 1, result.output
    assert "require --engine-preview" in " ".join(result.output.split())


@pytest.mark.parametrize(
    "value", ["packaging_mode=hatchling-vcs", "library.packaging_mode"]
)
def test_malformed_component_option_is_a_usage_error(
    value: str, tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "library",
            "--component-option",
            value,
        ],
    )

    assert result.exit_code == 2, result.output
    assert captured_selection == {}
    assert not (tmp_path / "p").exists()


def test_component_option_value_reaches_projectspec_under_the_declaring_id(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "library",
            "--component-option",
            "library.packaging_mode=hatchling-vcs",
        ],
    )

    assert captured_selection["component_options"] == {
        "library": {"packaging_mode": "hatchling-vcs"}
    }


def test_repeated_component_option_takes_the_last_value(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "library",
            "--component-option",
            "library.packaging_mode=uv-build-static",
            "--component-option",
            "library.packaging_mode=hatchling-vcs",
        ],
    )

    assert captured_selection["component_options"] == {
        "library": {"packaging_mode": "hatchling-vcs"}
    }


def test_unknown_component_option_owner_is_rejected_before_any_effect(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "cli",
            "--component-option",
            "not-a-component.x=1",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "Unknown --component-option component 'not-a-component'" in result.output
    assert captured_selection == {}
    assert not (tmp_path / "p").exists()


def test_component_option_for_an_unselected_owner_is_rejected(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    result = runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "cli",
            "--component-option",
            "library.packaging_mode=hatchling-vcs",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "is not selected" in result.output
    assert captured_selection == {}


def test_undeclared_option_name_reaches_the_engine(tmp_path: Path) -> None:
    """An option name no descriptor declares is the engine's verdict, not a
    client-side check -- it must produce the engine's own message.
    """
    result = runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "library",
            "--component-option",
            "library.not_a_real_option=1",
        ],
    )

    assert result.exit_code == 1, result.output
    assert "not_a_real_option" in result.output
    assert not (tmp_path / "p").exists()


def test_a_selected_optionless_component_serialises_no_namespace(
    tmp_path: Path, captured_selection: dict[str, object]
) -> None:
    """`data-science` and `jupiter` both declare no options -- the pipeline
    must receive `None`, not `{}` and not `{"jupyter": {}}`.
    """
    runner.invoke(
        app,
        [
            "new",
            "Risk Models",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "data-science",
            "--capability",
            "jupyter",
        ],
    )

    assert captured_selection["component_options"] is None


def test_colliding_option_names_stay_unambiguous(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    captured_selection: dict[str, object],
) -> None:
    """An archetype and a capability that both declare an option called
    `shared` each receive their own value, routed by the owner id.
    """
    descriptors = (
        _descriptor("arch-x", "archetype", options=(_option("shared"),)),
        _descriptor("cap-x", "capability", options=(_option("shared"),)),
    )
    _install_synthetic_catalogue(monkeypatch, descriptors)

    runner.invoke(
        app,
        [
            "new",
            "X",
            "--path",
            str(tmp_path / "p"),
            *_YES_DATA,
            "--engine-preview",
            "--archetype",
            "arch-x",
            "--capability",
            "cap-x",
            "--component-option",
            "arch-x.shared=archetype-value",
            "--component-option",
            "cap-x.shared=capability-value",
        ],
    )

    assert captured_selection["component_options"] == {
        "arch-x": {"shared": "archetype-value"},
        "cap-x": {"shared": "capability-value"},
    }


def test_component_options_are_collected_after_all_other_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    captured_selection: dict[str, object],
) -> None:
    """Prompt order: capabilities -> project answers -> the archetype's own
    options, last (CF-13.04, ADR 0029). `library` declares two.
    """
    order: list[str] = []

    def fake_checkbox(message: str, **_kw: object) -> _Reply:
        order.append(message)
        return _Reply([])

    def fake_text(message: str, **_kw: object) -> _Reply:
        order.append(message)
        return _Reply("Engine Preview" if message == "Project name" else "0.1.0")

    def fake_select(message: str, **_kw: object) -> _Reply:
        order.append(message)
        return _Reply("mit" if message == "License" else "hatchling-vcs")

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
            "library",
        ],
    )

    assert order[:4] == [
        "Which capabilities?",
        "Project name",
        "Short description",
        "License",
    ]
    # `library`'s own two declared options are prompted last, after everything.
    assert len(order) == 6
    assert "component_options" in captured_selection
