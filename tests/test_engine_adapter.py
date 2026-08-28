"""`engine.py` -- protocol negotiation, parsing, validation, and error text.

Exercises the real `forge_template` package (the `engine` dev-group
dependency, present by default per `[tool.uv] default-groups = ["dev"]").
This is deliberately not network-marked: the dependency was already resolved
at `uv sync` time from a pinned commit, so importing it here makes no network
call of its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from forge_template import (
    ComponentDescriptor,
    ComponentOption,
    ComponentRelation,
    EngineErrorCode,
    EngineInfo,
    ForgeEngineError,
)

from create_forge import engine
from create_forge.spec import build_spec_payload

_VALID_ANSWERS = {
    "project_name": "Credit Risk Utils",
    "project_description": "Shared credit-risk calculations.",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
    "python_min_version": "3.11",
    "python_version": "3.13",
}


def _engine_info(
    *,
    package_version: str = "0.2.0",
    projectspec_protocols: tuple[int, ...] = (1,),
    component_manifest_protocols: tuple[int, ...] = (1,),
) -> EngineInfo:
    return EngineInfo(
        package_version=package_version,
        projectspec_protocols=projectspec_protocols,
        component_manifest_protocols=component_manifest_protocols,
    )


def test_negotiate_protocol_accepts_the_real_installed_engine() -> None:
    """No exception -- the installed 0.2.0 engine and this CLI both speak
    protocol 1 today.
    """
    engine.negotiate_protocol()


def test_negotiate_protocol_rejects_an_untested_package_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engine,
        "get_engine_info",
        lambda: _engine_info(package_version="0.2.1"),
    )

    with pytest.raises(
        engine.EngineCompatibilityError,
        match=r"0\.2\.1.*tested only with forge-template 0\.2\.0",
    ):
        engine.negotiate_protocol()


def test_negotiate_protocol_rejects_a_disjoint_protocol_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engine,
        "get_engine_info",
        lambda: EngineInfo(
            package_version="0.2.0",
            projectspec_protocols=(2,),
            component_manifest_protocols=(1,),
        ),
    )

    with pytest.raises(engine.EngineCompatibilityError, match="protocol"):
        engine.negotiate_protocol()


def test_discover_returns_the_real_empty_production_catalogue() -> None:
    """Stage 08 has not shipped a production manifest yet."""
    assert engine.discover() == ()


def test_discover_preserves_public_component_descriptors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    info_calls = 0

    def get_info() -> EngineInfo:
        nonlocal info_calls
        info_calls += 1
        return _engine_info()

    descriptors = (
        ComponentDescriptor(
            id="library",
            name="Python Library",
            description="A reusable Python package.",
            kind="archetype",
            version="1.0.0",
            projectspec_protocols=(1,),
            requires_python=">=3.11",
            requires=(ComponentRelation(id="documentation", version=">=1,<2"),),
            conflicts=(ComponentRelation(id="application"),),
            options=(
                ComponentOption(
                    name="build_backend",
                    type="string",
                    required=True,
                    default="uv_build",
                    choices=("uv_build", "hatchling"),
                    description="Build backend.",
                ),
            ),
        ),
        ComponentDescriptor(
            id="documentation",
            name="Documentation",
            description="A documentation site.",
            kind="capability",
            version="1.0.0",
            projectspec_protocols=(1,),
            requires_python=">=3.11",
            requires=(),
            conflicts=(),
            options=(),
        ),
        ComponentDescriptor(
            id="github",
            name="GitHub",
            description="GitHub repository integration.",
            kind="platform",
            version="1.0.0",
            projectspec_protocols=(1,),
            requires_python=">=3.11",
            requires=(),
            conflicts=(),
            options=(),
        ),
    )
    monkeypatch.setattr(engine, "get_engine_info", get_info)
    monkeypatch.setattr(engine, "_discover_components", lambda: descriptors)

    discovered = engine.discover()

    assert info_calls == 1
    assert discovered is descriptors
    assert [component.kind for component in discovered] == [
        "archetype",
        "capability",
        "platform",
    ]
    assert discovered[0].id == "library"
    assert discovered[0].name == "Python Library"
    assert discovered[0].requires[0].id == "documentation"
    assert discovered[0].conflicts[0].id == "application"
    assert discovered[0].options[0].name == "build_backend"


@pytest.mark.parametrize(
    ("info", "message"),
    [
        (_engine_info(projectspec_protocols=(2,)), "ProjectSpec"),
        (
            _engine_info(component_manifest_protocols=(2,)),
            "component manifest",
        ),
    ],
)
def test_discover_rejects_incompatible_protocols_before_catalogue_access(
    monkeypatch: pytest.MonkeyPatch,
    info: EngineInfo,
    message: str,
) -> None:
    discovered = False

    def fake_discover() -> tuple[ComponentDescriptor, ...]:
        nonlocal discovered
        discovered = True
        return ()

    monkeypatch.setattr(engine, "get_engine_info", lambda: info)
    monkeypatch.setattr(engine, "_discover_components", fake_discover)

    with pytest.raises(engine.EngineCompatibilityError, match=message) as excinfo:
        engine.discover()

    assert discovered is False
    assert "forge-template 0.2.0" in str(excinfo.value)
    assert "[2]" in str(excinfo.value)
    assert "[1]" in str(excinfo.value)


def test_discover_propagates_structured_engine_failure_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = ForgeEngineError(
        code=EngineErrorCode.COMPONENT_DISCOVERY_FAILED,
        operation="discover",
        message="The installed component catalogue is invalid.",
    )

    def fail_discovery() -> tuple[ComponentDescriptor, ...]:
        raise expected

    monkeypatch.setattr(engine, "get_engine_info", _engine_info)
    monkeypatch.setattr(engine, "_discover_components", fail_discovery)

    with pytest.raises(ForgeEngineError) as excinfo:
        engine.discover()

    assert excinfo.value is expected


def test_build_project_spec_parses_a_complete_payload() -> None:
    payload = build_spec_payload(_VALID_ANSWERS, archetype="library")

    spec = engine.build_project_spec(payload)

    assert spec.protocol_version == 1
    assert spec.project.name == "Credit Risk Utils"
    assert spec.project.package_name == "credit_risk_utils"
    assert spec.components.archetype == "library"


def test_build_project_spec_negotiates_before_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An incompatible engine is rejected before the payload is even looked
    at, satisfying #46's "negotiate ... before any side effect" criterion.
    """
    monkeypatch.setattr(
        engine,
        "get_engine_info",
        lambda: EngineInfo(
            package_version="0.2.0",
            projectspec_protocols=(2,),
            component_manifest_protocols=(1,),
        ),
    )

    with pytest.raises(engine.EngineCompatibilityError):
        engine.build_project_spec({"this": "is not even a valid shape"})


def test_build_project_spec_translates_a_malformed_payload() -> None:
    """A payload missing a required field raises the engine's own structured
    `ForgeEngineError`, located at the missing field -- not a bare KeyError
    or a create-forge-invented message.
    """
    payload = build_spec_payload({}, archetype="library")  # no project_name

    with pytest.raises(ForgeEngineError) as excinfo:
        engine.build_project_spec(payload)

    exc = excinfo.value
    assert exc.code.value == "invalid-project-spec"
    assert exc.details
    assert any("project" in detail.path for detail in exc.details)


def test_validate_fails_closed_against_the_empty_catalogue() -> None:
    """`forge-template` 0.2.0 ships an intentionally empty production
    catalogue (Stage 08 adds the first manifest), so validating any
    archetype selection fails today -- by design, not by bug. This test is
    expected to start failing the moment a real 'library' manifest exists;
    when it does, replace it with an assertion that validation succeeds.
    """
    payload = build_spec_payload(_VALID_ANSWERS, archetype="library")
    spec = engine.build_project_spec(payload)

    with pytest.raises(ForgeEngineError) as excinfo:
        engine.validate(spec)

    assert excinfo.value.code.value == "invalid-component-selection"


def test_render_fails_closed_without_writing_against_the_empty_catalogue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = build_spec_payload(_VALID_ANSWERS, archetype="library")
    spec = engine.build_project_spec(payload)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ForgeEngineError) as excinfo:
        engine.render(spec)

    assert excinfo.value.code is EngineErrorCode.INVALID_COMPONENT_SELECTION
    assert list(tmp_path.iterdir()) == []


def test_explain_formats_code_and_located_details() -> None:
    payload = build_spec_payload({}, archetype="library")

    with pytest.raises(ForgeEngineError) as excinfo:
        engine.build_project_spec(payload)

    text = engine.explain(excinfo.value)

    assert "invalid-project-spec" in text
    assert "project" in text
