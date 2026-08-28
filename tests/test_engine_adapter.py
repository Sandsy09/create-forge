"""`engine.py` -- protocol negotiation, parsing, validation, and error text.

Exercises the real `forge_template` package (the `engine` dev-group
dependency, present by default per `[tool.uv] default-groups = ["dev"]").
This is deliberately not network-marked: the dependency was already resolved
at `uv sync` time from a pinned commit, so importing it here makes no network
call of its own.
"""

from __future__ import annotations

import pytest
from forge_template import EngineInfo, ForgeEngineError

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


def test_negotiate_protocol_accepts_the_real_installed_engine() -> None:
    """No exception -- the installed 0.2.0 engine and this CLI both speak
    protocol 1 today.
    """
    engine.negotiate_protocol()


def test_negotiate_protocol_rejects_a_disjoint_protocol_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engine,
        "get_engine_info",
        lambda: EngineInfo(
            package_version="9.0.0",
            projectspec_protocols=(2,),
            component_manifest_protocols=(1,),
        ),
    )

    with pytest.raises(engine.EngineCompatibilityError, match="protocol"):
        engine.negotiate_protocol()


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
            package_version="9.0.0",
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


def test_explain_formats_code_and_located_details() -> None:
    payload = build_spec_payload({}, archetype="library")

    with pytest.raises(ForgeEngineError) as excinfo:
        engine.build_project_spec(payload)

    text = engine.explain(excinfo.value)

    assert "invalid-project-spec" in text
    assert "project" in text
