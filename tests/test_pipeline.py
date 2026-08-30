"""`pipeline.build_generation_request`/`finalise_generation_request` --
orchestration order, staging/finalisation (ADR 0015), legacy Library option
derivation (CF-08.02), and the real, end-to-end success against
`forge-template`'s production catalogue.

Exercises the real `forge_template` package -- the `engine` optional extra
(ADR 0018), present when `uv sync --all-extras` was used to set up this
checkout -- mirroring `tests/test_engine_adapter.py`'s style.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from forge_template import (
    ComponentDescriptor,
    ComponentOption,
    ComponentOwner,
    GenerationPlan,
    PlannedFile,
    RenderedFile,
    RenderedProject,
)

from create_forge import engine, pipeline
from create_forge.pipeline import (
    GenerationRequest,
    build_generation_request,
    finalise_generation_request,
)
from create_forge.staging import DestinationConflictError

_VALID_ANSWERS = {
    "project_name": "Credit Risk Utils",
    "project_description": "Shared credit-risk calculations.",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
    "python_min_version": "3.11",
    "python_version": "3.13",
}


def _descriptor(
    component_id: str, *, options: tuple[ComponentOption, ...] = ()
) -> ComponentDescriptor:
    """A minimal `ComponentDescriptor` for `_resolved_component_options` tests.

    Only `id` and `options` matter to that function; every other field is a
    plausible placeholder.
    """
    return ComponentDescriptor(
        id=component_id,
        name=component_id.title(),
        description=f"{component_id} archetype.",
        kind="archetype",
        version="1.0.0",
        projectspec_protocols=(1,),
        requires_python=">=3.11",
        requires=(),
        conflicts=(),
        options=options,
    )


_PACKAGING_MODE_OPTION = ComponentOption(
    name="packaging_mode",
    type="string",
    required=False,
    default="uv-build-static",
    choices=("uv-build-static", "hatchling-static", "hatchling-vcs"),
    description="How the package is built and versioned.",
)


def test_build_generation_request_calls_the_pipeline_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """discover -> build -> validate -> render, in that order, each receiving
    the previous stage's output.
    """
    calls: list[str] = []

    def fake_discover() -> tuple[Any, ...]:
        calls.append("discover")
        return ()

    def fake_build_project_spec(payload: dict[str, object]) -> str:
        calls.append("build")
        assert payload["components"] == {
            "archetype": "library",
            "capabilities": [],
            "platforms": [],
        }
        return "parsed-spec"

    def fake_validate(spec: str) -> str:
        calls.append("validate")
        assert spec == "parsed-spec"
        return "validated-spec"

    def fake_render(spec: str) -> str:
        calls.append("render")
        assert spec == "validated-spec"
        return "rendered-project"

    monkeypatch.setattr(engine, "discover", fake_discover)
    monkeypatch.setattr(engine, "build_project_spec", fake_build_project_spec)
    monkeypatch.setattr(engine, "validate", fake_validate)
    monkeypatch.setattr(engine, "render", fake_render)

    result = build_generation_request(_VALID_ANSWERS, archetype="library")

    assert calls == ["discover", "build", "validate", "render"]
    assert isinstance(result, GenerationRequest)
    # The fakes above return plain strings, not real ProjectSpec/RenderedProject
    # instances -- this test only cares that each stage's output reaches the
    # next, not that the types line up (real types are exercised end-to-end by
    # test_build_generation_request_fails_closed_against_the_empty_catalogue).
    # cast(Any, ...) sidesteps mypy's strict_equality on the deliberately
    # mismatched fake values, without also disabling the reachability check
    # a `# type: ignore[comparison-overlap]` would.
    assert cast(Any, result.spec) == "validated-spec"
    assert cast(Any, result.rendered) == "rendered-project"


def test_build_generation_request_passes_component_selection_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_payload: dict[str, object] = {}

    def fake_build_project_spec(payload: dict[str, object]) -> str:
        seen_payload.update(payload)
        return "spec"

    monkeypatch.setattr(engine, "discover", lambda: ())
    monkeypatch.setattr(engine, "build_project_spec", fake_build_project_spec)
    monkeypatch.setattr(engine, "validate", lambda spec: spec)
    monkeypatch.setattr(engine, "render", lambda spec: "rendered")

    build_generation_request(
        _VALID_ANSWERS,
        archetype="library",
        capabilities=["documentation"],
        platforms=["github"],
        component_options={"library": {"build_backend": "uv_build"}},
    )

    assert seen_payload["components"] == {
        "archetype": "library",
        "capabilities": ["documentation"],
        "platforms": ["github"],
    }
    assert seen_payload["component_options"] == {
        "library": {"build_backend": "uv_build"}
    }


@pytest.mark.parametrize("archetype", ["library", "cli"])
def test_build_generation_request_succeeds_against_the_real_catalogue(
    archetype: str,
) -> None:
    """The real, unmocked engine: `forge-template` 0.3.0's production
    catalogue ships both reference archetypes (CF-08.02), replacing the
    Stage 06-era empty-catalogue rejection this test's own docstring
    anticipated retiring.
    """
    request = pipeline.build_generation_request(_VALID_ANSWERS, archetype=archetype)

    assert request.spec.components.archetype == archetype
    assert any(file.target == "pyproject.toml" for file in request.rendered.files)


def test_build_generation_request_derives_legacy_library_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no caller-supplied `component_options`, `library` gets its
    `packaging_mode` derived from the legacy `build_backend`/`versioning`
    answers via the engine's own `map_legacy_library_answers` -- gated on
    `library`'s own discovered descriptor declaring that option name
    (CF-08.03, ADR 0019), not on a hardcoded archetype id.
    """
    seen_payload: dict[str, object] = {}

    def fake_build_project_spec(payload: dict[str, object]) -> str:
        seen_payload.update(payload)
        return "spec"

    monkeypatch.setattr(
        engine,
        "discover",
        lambda: (_descriptor("library", options=(_PACKAGING_MODE_OPTION,)),),
    )
    monkeypatch.setattr(engine, "build_project_spec", fake_build_project_spec)
    monkeypatch.setattr(engine, "validate", lambda spec: spec)
    monkeypatch.setattr(engine, "render", lambda spec: "rendered")
    monkeypatch.setattr(
        engine,
        "map_legacy_library_options",
        lambda legacy: {"packaging_mode": "hatchling-vcs"},
    )

    answers = {**_VALID_ANSWERS, "build_backend": "hatchling", "versioning": "vcs"}
    build_generation_request(answers, archetype="library")

    assert seen_payload["component_options"] == {
        "library": {"packaging_mode": "hatchling-vcs"}
    }


def test_build_generation_request_derives_options_for_a_non_library_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF-08.03 (ADR 0019): the derivation is gated on the selected
    archetype's own discovered descriptor declaring `packaging_mode`, not on
    a hardcoded `"library"` id. A differently-named archetype that declares
    the same option still receives the mapping -- impossible under the prior
    `archetype != "library"` branch, so this is the test that would fail if
    that literal ever came back.
    """
    seen_payload: dict[str, object] = {}

    def fake_build_project_spec(payload: dict[str, object]) -> str:
        seen_payload.update(payload)
        return "spec"

    monkeypatch.setattr(
        engine,
        "discover",
        lambda: (_descriptor("package", options=(_PACKAGING_MODE_OPTION,)),),
    )
    monkeypatch.setattr(engine, "build_project_spec", fake_build_project_spec)
    monkeypatch.setattr(engine, "validate", lambda spec: spec)
    monkeypatch.setattr(engine, "render", lambda spec: "rendered")
    monkeypatch.setattr(
        engine,
        "map_legacy_library_options",
        lambda legacy: {"packaging_mode": "hatchling-vcs"},
    )

    answers = {**_VALID_ANSWERS, "build_backend": "hatchling", "versioning": "vcs"}
    build_generation_request(answers, archetype="package")

    assert seen_payload["component_options"] == {
        "package": {"packaging_mode": "hatchling-vcs"}
    }


def test_build_generation_request_does_not_derive_options_for_other_archetypes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`cli` has no options (CF-08.02): the legacy Library mapping must not
    fire for an archetype whose own discovered descriptor declares no
    options, even when legacy answers are present.
    """
    seen_payload: dict[str, object] = {}

    def fake_build_project_spec(payload: dict[str, object]) -> str:
        seen_payload.update(payload)
        return "spec"

    def unexpected_mapping(_legacy: object) -> object:
        raise AssertionError(
            "map_legacy_library_options ran for an archetype with no options"
        )

    monkeypatch.setattr(engine, "discover", lambda: (_descriptor("cli"),))
    monkeypatch.setattr(engine, "build_project_spec", fake_build_project_spec)
    monkeypatch.setattr(engine, "validate", lambda spec: spec)
    monkeypatch.setattr(engine, "render", lambda spec: "rendered")
    monkeypatch.setattr(engine, "map_legacy_library_options", unexpected_mapping)

    answers = {**_VALID_ANSWERS, "build_backend": "hatchling", "versioning": "vcs"}
    build_generation_request(answers, archetype="cli")

    assert "component_options" not in seen_payload


def test_build_generation_request_skips_a_mapping_the_descriptor_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF-08.03 (ADR 0019): an archetype that declares options, but not the
    ones the legacy mapping produces, must not receive that mapping either --
    the subset check, not merely "has some options", is what gates it.
    """
    seen_payload: dict[str, object] = {}

    def fake_build_project_spec(payload: dict[str, object]) -> str:
        seen_payload.update(payload)
        return "spec"

    unrelated_option = ComponentOption(
        name="template_engine",
        type="string",
        required=False,
        default="jinja",
        choices=(),
        description="Unrelated to the legacy packaging mapping.",
    )
    monkeypatch.setattr(
        engine, "discover", lambda: (_descriptor("web", options=(unrelated_option,)),)
    )
    monkeypatch.setattr(engine, "build_project_spec", fake_build_project_spec)
    monkeypatch.setattr(engine, "validate", lambda spec: spec)
    monkeypatch.setattr(engine, "render", lambda spec: "rendered")
    monkeypatch.setattr(
        engine,
        "map_legacy_library_options",
        lambda legacy: {"packaging_mode": "hatchling-vcs"},
    )

    answers = {**_VALID_ANSWERS, "build_backend": "hatchling", "versioning": "vcs"}
    build_generation_request(answers, archetype="web")

    assert "component_options" not in seen_payload


def test_build_generation_request_leaves_explicit_component_options_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit `component_options` always wins -- the legacy derivation
    is strictly a fallback for the caller-supplies-nothing case (CF-08.02).
    """
    seen_payload: dict[str, object] = {}

    def fake_build_project_spec(payload: dict[str, object]) -> str:
        seen_payload.update(payload)
        return "spec"

    def unexpected_mapping(_legacy: object) -> object:
        raise AssertionError(
            "map_legacy_library_options ran despite an explicit override"
        )

    monkeypatch.setattr(engine, "discover", lambda: ())
    monkeypatch.setattr(engine, "build_project_spec", fake_build_project_spec)
    monkeypatch.setattr(engine, "validate", lambda spec: spec)
    monkeypatch.setattr(engine, "render", lambda spec: "rendered")
    monkeypatch.setattr(engine, "map_legacy_library_options", unexpected_mapping)

    answers = {**_VALID_ANSWERS, "build_backend": "hatchling", "versioning": "vcs"}
    build_generation_request(
        answers,
        archetype="library",
        component_options={"library": {"packaging_mode": "uv-build-static"}},
    )

    assert seen_payload["component_options"] == {
        "library": {"packaging_mode": "uv-build-static"}
    }


def test_discover_archetypes_filters_to_archetype_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archetype_descriptor = ComponentDescriptor(
        id="library",
        name="Library",
        description="An installable Python package.",
        kind="archetype",
        version="1.0.0",
        projectspec_protocols=(1,),
        requires_python=">=3.11",
        requires=(),
        conflicts=(),
        options=(),
    )
    capability_descriptor = ComponentDescriptor(
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
    )
    monkeypatch.setattr(
        engine, "discover", lambda: (archetype_descriptor, capability_descriptor)
    )

    assert pipeline.discover_archetypes() == (archetype_descriptor,)


def _synthetic_request() -> GenerationRequest:
    """A `GenerationRequest` built from the real public models, entirely
    without a component catalogue -- `finalise_generation_request` only
    needs `request.rendered.files`, so this stands in for a real render.
    """
    owner = ComponentOwner(id="library")
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner=owner),
            PlannedFile(target="src/pkg/__init__.py", owner=owner),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(
            RenderedFile(target="pyproject.toml", content=b"[project]\n"),
            RenderedFile(target="src/pkg/__init__.py", content=b""),
        ),
    )
    # A real `ProjectSpec` plays no part in finalisation -- only
    # `request.rendered.files` does -- so a plain placeholder stands in,
    # the same `cast(Any, ...)` pattern used above.
    return GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)


def test_finalise_generation_request_stages_and_moves_into_place(
    tmp_path: Path,
) -> None:
    request = _synthetic_request()
    dst = tmp_path / "proj"

    finalise_generation_request(request, dst)

    assert (dst / "pyproject.toml").read_bytes() == b"[project]\n"
    assert (dst / "src" / "pkg" / "__init__.py").exists()
    # Nothing but the destination itself was left behind next to it.
    assert list(tmp_path.iterdir()) == [dst]


def test_finalise_generation_request_rejects_a_non_empty_destination(
    tmp_path: Path,
) -> None:
    request = _synthetic_request()
    dst = tmp_path / "proj"
    dst.mkdir()
    (dst / "existing.txt").write_text("hi", encoding="utf-8")

    with pytest.raises(DestinationConflictError):
        finalise_generation_request(request, dst)

    # The pre-existing destination is untouched.
    assert list(dst.iterdir()) == [dst / "existing.txt"]


def test_finalise_generation_request_leaves_nothing_on_a_mid_write_failure(
    tmp_path: Path,
) -> None:
    """A target that escapes the staging root fails `write_files` partway
    through; nothing must survive at or beside `dst`.
    """
    owner = ComponentOwner(id="library")
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="ok.txt", owner=owner),
            PlannedFile(target="../escape.txt", owner=owner),
        ),
    )
    rendered = RenderedProject(
        plan=plan,
        files=(
            RenderedFile(target="ok.txt", content=b"fine"),
            RenderedFile(target="../escape.txt", content=b"malicious"),
        ),
    )
    request = GenerationRequest(spec=cast(Any, "unused-spec"), rendered=rendered)
    dst = tmp_path / "proj"

    with pytest.raises(Exception, match="refusing to write"):
        finalise_generation_request(request, dst)

    assert not dst.exists()
    assert list(tmp_path.iterdir()) == []
