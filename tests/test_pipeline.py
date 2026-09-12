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

import create_forge.staging as staging_module
from create_forge import engine, pipeline
from create_forge.pipeline import (
    Catalogue,
    GenerationRequest,
    build_generation_request,
    finalise_generation_request,
)
from create_forge.spec import SelectionKind, SelectionRequest
from create_forge.staging import DestinationConflictError, StagingError

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

    result = build_generation_request(
        _VALID_ANSWERS, selection=SelectionRequest.of(archetype="library")
    )

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
        selection=SelectionRequest.of(
            archetype="library",
            capabilities=["documentation"],
            platforms=["github"],
        ),
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


def _real_archetype_selections() -> list[tuple[str, tuple[str, ...]]]:
    """Every discovered archetype with its own discovered required
    capabilities -- CF-13.05 generalised the parametrisation below from a
    hardcoded `("library", "cli")` pair so Data Science (which requires
    `jupyter`) traverses the real pipeline too, with no requirement id named
    here.
    """
    catalogue = Catalogue(tuple(engine.discover()))
    return [
        (d.id, catalogue.required_ids(d.id, SelectionKind.CAPABILITIES))
        for d in catalogue.archetypes
    ]


@pytest.mark.parametrize(
    ("archetype", "required_capabilities"), _real_archetype_selections()
)
def test_build_generation_request_succeeds_against_the_real_catalogue(
    archetype: str, required_capabilities: tuple[str, ...]
) -> None:
    """The real, unmocked engine: the installed `forge-template` production
    catalogue (since 0.3.0, CF-08.02; five components since 0.4.0, CF-13.01)
    ships every archetype this parametrisation discovers, each generated with
    its own discovered requirements satisfied.
    """
    request = pipeline.build_generation_request(
        _VALID_ANSWERS,
        selection=SelectionRequest.of(
            archetype=archetype, capabilities=required_capabilities
        ),
    )

    assert request.spec.components.archetype == archetype
    assert tuple(request.spec.components.capabilities) == required_capabilities
    assert any(file.target == "pyproject.toml" for file in request.rendered.files)


def test_build_generation_request_passes_component_options_through_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0040 decision 10 (CF-18.01) retires the legacy `build_backend`/
    `versioning` -> `packaging_mode` fallback this pipeline used to fill in:
    `component_options` the caller supplies now passes straight through, and
    an archetype option the caller left unset simply stays unset.
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

    build_generation_request(
        _VALID_ANSWERS,
        selection=SelectionRequest.of(archetype="library"),
        component_options={"library": {"packaging_mode": "uv-build-static"}},
    )

    assert seen_payload["component_options"] == {
        "library": {"packaging_mode": "uv-build-static"}
    }

    seen_payload.clear()
    build_generation_request(
        _VALID_ANSWERS, selection=SelectionRequest.of(archetype="library")
    )
    assert "component_options" not in seen_payload


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


def test_build_generation_request_reuses_a_supplied_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CF-13.03 / ADR 0028: `cli.py` discovers a `Catalogue` once for
    selection and hands it straight to `build_generation_request`, so
    `engine.discover()` is not called a second time.
    """
    calls = 0

    def counting_discover() -> tuple[ComponentDescriptor, ...]:
        nonlocal calls
        calls += 1
        return (_descriptor("library", options=(_PACKAGING_MODE_OPTION,)),)

    monkeypatch.setattr(engine, "discover", counting_discover)
    monkeypatch.setattr(engine, "build_project_spec", lambda payload: payload)
    monkeypatch.setattr(engine, "validate", lambda spec: spec)
    monkeypatch.setattr(engine, "render", lambda spec: "rendered")

    catalogue = pipeline.discover_catalogue()
    assert calls == 1

    build_generation_request(
        _VALID_ANSWERS,
        selection=SelectionRequest.of(archetype="library"),
        catalogue=catalogue,
    )

    assert calls == 1  # not re-discovered inside build_generation_request


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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _synthetic_request()
    dst = tmp_path / "proj"

    def fake_lock(staging_dir: Path) -> None:
        assert staging_dir != dst
        assert not dst.exists()
        assert (staging_dir / "pyproject.toml").is_file()
        (staging_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")

    monkeypatch.setattr(staging_module, "create_uv_lock", fake_lock)

    finalise_generation_request(request, dst)

    assert (dst / "pyproject.toml").read_bytes() == b"[project]\n"
    assert (dst / "src" / "pkg" / "__init__.py").exists()
    assert (dst / "uv.lock").read_text(encoding="utf-8") == "version = 1\n"
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


def test_finalise_generation_request_cleans_up_a_lock_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _synthetic_request()
    dst = tmp_path / "proj"

    def failing_lock(staging_dir: Path) -> None:
        assert (staging_dir / "pyproject.toml").is_file()
        raise StagingError("uv lock failed with exit status 2")

    monkeypatch.setattr(staging_module, "create_uv_lock", failing_lock)

    with pytest.raises(StagingError, match="uv lock failed"):
        finalise_generation_request(request, dst)

    assert not dst.exists()
    assert list(tmp_path.iterdir()) == []
