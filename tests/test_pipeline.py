"""`pipeline.build_generation_request`/`finalise_generation_request` --
orchestration order, staging/finalisation (ADR 0015), and the real,
end-to-end characterized failure against `forge-template`'s empty catalogue.

Exercises the real `forge_template` package (the `engine` dev-group
dependency, present by default per `[tool.uv] default-groups = ["dev"]`),
mirroring `tests/test_engine_adapter.py`'s style.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from forge_template import (
    ForgeEngineError,
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


def _synthetic_request() -> GenerationRequest:
    """A `GenerationRequest` built from the real public models, entirely
    without a component catalogue -- `finalise_generation_request` only
    needs `request.rendered.files`, so this stands in for a real render.
    """
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="pyproject.toml", owner_component_id="library"),
            PlannedFile(target="src/pkg/__init__.py", owner_component_id="library"),
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
    plan = GenerationPlan(
        component_order=("library",),
        files=(
            PlannedFile(target="ok.txt", owner_component_id="library"),
            PlannedFile(target="../escape.txt", owner_component_id="library"),
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
