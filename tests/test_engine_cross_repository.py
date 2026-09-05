"""Executable create-forge/forge-template engine contract (ADR 0018).

The normal suite exercises the released `forge-template>=0.4.1,<0.5` range
(ADR 0031) resolved into ``uv.lock`` from PyPI. The sibling-checkout command in
``docs/cross-repository-workflow.md`` installs both working trees in
isolation and runs this same file against pending local changes without
exposing forge-template's private fixture-catalogue seam.
"""

from __future__ import annotations

import re
import typing
from collections.abc import Callable

import pytest
from forge_template import (
    ComponentDescriptor,
    ComponentOption,
    ComponentOwner,
    ComponentRelation,
    ComponentSelection,
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
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from create_forge import compat, engine
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
    package_version: str = "0.4.1",
    projectspec_protocols: tuple[int, ...] = (1,),
    component_manifest_protocols: tuple[int, ...] = (1,),
) -> EngineInfo:
    return EngineInfo(
        package_version=package_version,
        projectspec_protocols=projectspec_protocols,
        component_manifest_protocols=component_manifest_protocols,
    )


def test_real_engine_matches_the_supported_range() -> None:
    """ADR 0018 assigned the first released range; ADR 0026 moved it to the
    `forge-template` 0.4 line. The installed engine must fall within the
    declared range and advertise a compatible protocol pair."""
    info = get_engine_info()

    assert info.package_version == "0.4.1"
    assert Version(info.package_version) in SpecifierSet(compat.SUPPORTED_ENGINE_RANGE)
    assert set(info.projectspec_protocols) & set(compat.SUPPORTED_PROJECTSPEC_PROTOCOLS)
    assert set(info.component_manifest_protocols) & set(
        compat.SUPPORTED_COMPONENT_MANIFEST_PROTOCOLS
    )
    assert _spec().protocol_version == 1

    descriptors = engine.discover()
    discovered = {descriptor.id for descriptor in descriptors}
    assert {"library", "cli"} <= discovered

    # The 0.4 line is the first to ship a reusable capability alongside
    # archetypes, and the first whose catalogue declares a requirement
    # relationship. Asserted by descriptor kind and relationship shape,
    # never by component id -- CF-EPIC-13's acceptance forbids a catalogue
    # copy here, and CF-13.05 owns the Data Science proof itself.
    kinds = {descriptor.kind for descriptor in descriptors}
    assert "archetype" in kinds
    assert "capability" in kinds
    assert any(descriptor.requires for descriptor in descriptors)


def _string_constraint_pattern(annotated: object) -> str:
    """Pull the regex `pattern` off an `Annotated[str, StringConstraints(...)]`."""
    base, *metadata = typing.get_args(annotated)
    assert base is str
    for item in metadata:
        pattern = getattr(item, "pattern", None)
        if isinstance(pattern, str) and pattern:
            return pattern
    raise AssertionError(f"no StringConstraints pattern on {annotated!r}")


def test_selection_model_matches_the_documented_contract() -> None:
    """CF-13.02 / ADR 0027: the canonical `docs/component-selection.md`
    contract is built on a handful of engine facts. Pin them here -- from the
    public models, never by naming a component -- so a future engine change
    that invalidates the contract fails loudly rather than silently.
    """
    # Exactly three descriptor kinds -- `--capability` and `--platform` are
    # not speculative, and there is no fourth flag to design.
    kinds = set(typing.get_args(ComponentDescriptor.model_fields["kind"].annotation))
    assert kinds == {"archetype", "capability", "platform"}

    # `ComponentSelection` carries exactly the three fields the flags map onto.
    assert set(ComponentSelection.model_fields) == {
        "archetype",
        "capabilities",
        "platforms",
    }

    # A requirement edge names only an id -- its kind must be resolved back
    # through discovery, which is why the contract forbids a client-side kind
    # assumption.
    assert set(ComponentRelation.model_fields) == {"id", "version"}

    # Exactly four option value types. No `enum`, no `multi`: the client owns
    # coercing a CLI string to one of these before the strict engine sees it.
    option_types = set(typing.get_args(ComponentOption.model_fields["type"].annotation))
    assert option_types == {"string", "integer", "boolean", "string_list"}

    # `component_options` is a two-level mapping: component id -> option name
    # -> value. Owner namespacing already exists on the wire.
    outer = ProjectSpec.model_fields["component_options"].annotation
    owner_key, inner = typing.get_args(outer)
    option_key, _value = typing.get_args(inner)
    owner_pattern = _string_constraint_pattern(owner_key)
    option_pattern = _string_constraint_pattern(option_key)

    # The two identifier alphabets differ -- this is what makes `ID.OPTION`
    # unambiguous by construction, and the contract's split-on-first-dot rule
    # depends on it. Neither admits a dot; ids take `-`, option names take `_`.
    assert owner_pattern != option_pattern
    assert re.match(owner_pattern, "a.b") is None
    assert re.match(option_pattern, "a.b") is None
    assert re.match(owner_pattern, "a-b") is not None
    assert re.match(owner_pattern, "a_b") is None
    assert re.match(option_pattern, "a_b") is not None
    assert re.match(option_pattern, "a-b") is None


@pytest.mark.parametrize("package_version", ["0.4.0", "0.5.0"])
def test_untested_package_is_rejected_before_every_public_engine_call(
    monkeypatch: pytest.MonkeyPatch,
    package_version: str,
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
        lambda: _info(package_version=package_version),
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
    supported = re.escape(f"supports forge-template{compat.SUPPORTED_ENGINE_RANGE}")
    for operation in operations:
        with pytest.raises(
            engine.EngineCompatibilityError,
            match=rf"{re.escape(package_version)}.*{supported}",
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
