"""Executable create-forge/forge-template Stage 06 development contract.

The normal suite exercises the immutable Git dependency from ``uv.lock``.
The sibling-checkout command in ``docs/cross-repository-workflow.md`` installs
both working trees in isolation and runs this same file against pending local
changes without exposing forge-template's private fixture-catalogue seam.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from forge_template import EngineInfo, ProjectSpec, get_engine_info

from create_forge import engine
from create_forge.spec import build_spec_payload

_VALID_ANSWERS = {
    "project_name": "Contract Probe",
    "project_description": "Cross-repository engine contract.",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
    "python_min_version": "3.11",
    "python_version": "3.13",
}


def _spec() -> ProjectSpec:
    return engine.build_project_spec(
        build_spec_payload(_VALID_ANSWERS, archetype="library")
    )


def _info(
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


def test_real_engine_matches_the_exact_development_contract() -> None:
    info = get_engine_info()

    assert info.package_version == engine.TESTED_ENGINE_PACKAGE_VERSION == "0.2.0"
    assert set(info.projectspec_protocols) & set(engine.SUPPORTED_PROJECTSPEC_PROTOCOLS)
    assert set(info.component_manifest_protocols) & set(
        engine.SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS
    )
    assert _spec().protocol_version == 1
    assert engine.discover() == ()


def test_untested_package_is_rejected_before_every_public_engine_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec()
    invoked: list[str] = []

    def unexpected(name: str) -> Callable[..., object]:
        def call(*_args: object, **_kwargs: object) -> object:
            invoked.append(name)
            raise AssertionError(f"{name} ran before package compatibility failed")

        return call

    monkeypatch.setattr(
        engine,
        "get_engine_info",
        lambda: _info(package_version="0.2.1"),
    )
    monkeypatch.setattr(engine, "_parse_project_spec", unexpected("parse"))
    monkeypatch.setattr(engine, "_discover_components", unexpected("discover"))
    monkeypatch.setattr(engine, "_validate_project_spec", unexpected("validate"))
    monkeypatch.setattr(engine, "_render_project", unexpected("render"))

    operations = (
        lambda: engine.build_project_spec({}),
        engine.discover,
        lambda: engine.validate(spec),
        lambda: engine.render(spec),
    )
    for operation in operations:
        with pytest.raises(
            engine.EngineCompatibilityError,
            match=r"0\.2\.1.*tested only with forge-template 0\.2\.0",
        ):
            operation()

    assert invoked == []


@pytest.mark.parametrize(
    ("info", "message"),
    [
        (_info(projectspec_protocols=(2,)), "ProjectSpec"),
        (_info(component_manifest_protocols=(2,)), "component manifest"),
    ],
)
def test_render_rejects_unsupported_protocol_before_public_engine_call(
    monkeypatch: pytest.MonkeyPatch,
    info: EngineInfo,
    message: str,
) -> None:
    spec = _spec()
    rendered = False

    def unexpected_render(_spec: ProjectSpec) -> object:
        nonlocal rendered
        rendered = True
        raise AssertionError("render ran before protocol compatibility failed")

    monkeypatch.setattr(engine, "get_engine_info", lambda: info)
    monkeypatch.setattr(engine, "_render_project", unexpected_render)

    with pytest.raises(engine.EngineCompatibilityError, match=message):
        engine.render(spec)

    assert rendered is False
