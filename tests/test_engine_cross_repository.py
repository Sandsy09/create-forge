"""Executable create-forge/forge-template Stage 06 development contract.

The normal suite exercises the immutable Git dependency from ``uv.lock``.
The sibling-checkout command in ``docs/cross-repository-workflow.md`` installs
both working trees in isolation and runs this same file against pending local
changes without exposing forge-template's private fixture-catalogue seam.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from forge_template import (
    ComponentOwner,
    EngineInfo,
    ForgeEngineError,
    GenerationPlan,
    PlannedFile,
    ProjectSpec,
    RenderedFile,
    RenderedProject,
    get_engine_info,
    validate_rendered_project,
)

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
    package_version: str = "0.3.0",
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

    assert info.package_version == engine.TESTED_ENGINE_PACKAGE_VERSION == "0.3.0"
    assert set(info.projectspec_protocols) & set(engine.SUPPORTED_PROJECTSPEC_PROTOCOLS)
    assert set(info.component_manifest_protocols) & set(
        engine.SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS
    )
    assert _spec().protocol_version == 1
    discovered = {component.id for component in engine.discover()}
    assert {"library", "cli"} <= discovered


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
        lambda: _info(package_version="0.3.1"),
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
            match=r"0\.3\.1.*tested only with forge-template 0\.3\.0",
        ):
            operation()

    assert invoked == []


@pytest.mark.parametrize(
    ("info", "message"),
    [
        (_info(projectspec_protocols=(2,)), "ProjectSpec"),
        # 3 stays disjoint from SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS's
        # (1, 2) -- CF-08.02 widened that set, so a probe at 2 alone would no
        # longer be a rejection case.
        (_info(component_manifest_protocols=(3,)), "component manifest"),
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


def test_validate_rendered_project_is_the_adopted_generated_project_gate() -> None:
    """CF-07.04 (ADR 0015) adopted `forge-template`'s generated-project
    validation: `validate_rendered_project` is on the public facade, and a
    `RenderedProject` whose files don't match its own plan fails with
    `generated-project-invalid`. `render_project` calls this same function
    internally before returning (proven by `forge-template`'s own test
    suite, per docs/generated-project-validation.md) -- this is what lets
    `pipeline.finalise_generation_request` (ADR 0015) trust a
    `RenderedProject` it receives without revalidating it itself.
    """
    spec = _spec()
    owner = ComponentOwner(id="library")
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=owner),
            PlannedFile(target="README.md", owner=owner),
        ),
    )
    inconsistent = RenderedProject(
        plan=plan,
        # README.md is planned but missing from the rendered result.
        files=(RenderedFile(target="pyproject.toml", content=b"[project]\n"),),
    )

    with pytest.raises(ForgeEngineError) as excinfo:
        validate_rendered_project(spec, inconsistent)

    assert excinfo.value.code.value == "generated-project-invalid"
