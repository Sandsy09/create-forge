"""`pipeline.build_generation_request` -- orchestration order and the real,
end-to-end characterized failure against `forge-template`'s empty catalogue.

Exercises the real `forge_template` package (the `engine` dev-group
dependency, present by default per `[tool.uv] default-groups = ["dev"]`),
mirroring `tests/test_engine_adapter.py`'s style.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from forge_template import ForgeEngineError

from create_forge import engine, pipeline
from create_forge.pipeline import GenerationRequest, build_generation_request

_VALID_ANSWERS = {
    "project_name": "Credit Risk Utils",
    "project_description": "Shared credit-risk calculations.",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
    "python_min_version": "3.11",
    "python_version": "3.13",
}


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


def test_build_generation_request_fails_closed_against_the_empty_catalogue() -> None:
    """The real, unmocked engine: `forge-template` 0.2.0's production
    catalogue is intentionally empty until Stage 08, so the pipeline's
    `validate()` stage fails today -- by design, mirroring
    `tests/test_engine_adapter.py::test_validate_fails_closed_against_the_empty_catalogue`.
    This test is expected to start failing, not stay green, the moment a
    real 'library' manifest exists; replacing it with a success assertion at
    that point is expected maintenance.
    """
    with pytest.raises(ForgeEngineError) as excinfo:
        pipeline.build_generation_request(_VALID_ANSWERS, archetype="library")

    assert excinfo.value.code.value == "invalid-component-selection"
