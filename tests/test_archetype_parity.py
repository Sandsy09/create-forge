"""CF-08.03's archetype-parity review, made executable (ADR 0019).

Verifies, against the real installed `forge-template` engine (the `engine`
extra, present when `uv sync --all-extras` was used -- see
`tests/test_engine_adapter.py`'s own docstring), that `create-forge` remains
generic across the Library and CLI Application archetypes rather than
special-casing either one:

- both archetypes build structurally identical ProjectSpec payloads and run
  through one `build_generation_request` pipeline;
- component compatibility and discovery stay engine-owned -- see
  `tests/test_engine_adapter.py::test_discover_preserves_public_component_descriptors`
  for the deeper proof that descriptors pass through unchanged;
- `cli`'s discovered descriptor declares no options, and create-forge sends
  it none;
- no `command_name` field exists anywhere in this repository, and a `cli`
  render's console command is exactly `ProjectSpec.project.repository_name`;
- no shipped module hardcodes a component id to compare against -- the guard
  that would catch a regression of the branch CF-08.03 generalised in
  `pipeline._resolved_component_options`.
"""

from __future__ import annotations

import ast
from pathlib import Path

from create_forge import engine, pipeline
from create_forge.spec import SelectionRequest, build_spec_payload

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src" / "create_forge"
TEMPLATES_TOML = SRC_ROOT / "templates.toml"

# Every shipped module that could plausibly branch on a component identity --
# the discovery adapter itself, its two callers, and the spec/prompt layers
# selection flows through. `runner`/`registry`/`models`/`config`/`staging`
# never see a component id at all (they predate the engine or are Copier-only).
_SCANNED_MODULES = ("cli", "prompts", "pipeline", "spec", "engine")

_VALID_ANSWERS = {
    "project_name": "Credit Risk Utils",
    "project_description": "Shared credit-risk calculations.",
    "license": "mit",
    "author_name": "Test User",
    "author_email": "test@example.invalid",
    "python_min_version": "3.11",
    "python_version": "3.13",
}


def test_both_archetypes_build_the_same_projectspec_shape() -> None:
    """Criterion 3: one generic construction path. The only differences
    between a Library and a CLI Application payload are the archetype id
    itself and `component_options` -- every other section (`project`,
    `python`) is produced by the exact same code, unaware which archetype it
    is building for.
    """
    library_payload = build_spec_payload(_VALID_ANSWERS, archetype="library")
    cli_payload = build_spec_payload(_VALID_ANSWERS, archetype="cli")

    shared_keys = {"protocol_version", "project", "python"}
    for key in shared_keys:
        assert library_payload[key] == cli_payload[key]

    assert library_payload["components"] == {
        "archetype": "library",
        "capabilities": [],
        "platforms": [],
    }
    assert cli_payload["components"] == {
        "archetype": "cli",
        "capabilities": [],
        "platforms": [],
    }


def test_both_archetypes_render_through_the_one_shared_pipeline() -> None:
    """Criterion 3, end to end: `build_generation_request` is not
    archetype-branched -- both calls below run the identical function.
    """
    for archetype in ("library", "cli"):
        request = pipeline.build_generation_request(
            _VALID_ANSWERS, selection=SelectionRequest.of(archetype=archetype)
        )
        assert request.spec.components.archetype == archetype
        assert any(f.target == "pyproject.toml" for f in request.rendered.files)


def test_cli_archetype_declares_no_options_and_receives_none() -> None:
    """Criteria 2 and 4: `cli`'s own discovered descriptor is the source of
    truth for "no options" -- create-forge does not separately assert this
    about `cli`, it reads it.
    """
    descriptors = {d.id: d for d in engine.discover()}
    assert descriptors["cli"].options == ()

    request = pipeline.build_generation_request(
        _VALID_ANSWERS, selection=SelectionRequest.of(archetype="cli")
    )
    assert request.spec.component_options == {}


def test_no_command_name_field_exists_anywhere() -> None:
    """Criterion 5: the CLI Application contract derives its console command
    solely from `ProjectSpec.project.repository_name`. `create-forge` must
    never add a duplicate `command_name` input, model field, or registry
    prompt key for it.
    """
    for path in SRC_ROOT.glob("*.py"):
        assert "command_name" not in path.read_text(encoding="utf-8"), (
            f"{path.name} references command_name -- CLI Application command "
            "identity comes only from repository_name (see the canonical "
            "CLI Application archetype contract)."
        )
    assert "command_name" not in TEMPLATES_TOML.read_text(encoding="utf-8")


def test_cli_console_command_is_exactly_the_repository_name() -> None:
    """Criterion 5, proven against a real render rather than asserted about
    the contract in the abstract.
    """
    request = pipeline.build_generation_request(
        _VALID_ANSWERS, selection=SelectionRequest.of(archetype="cli")
    )
    repository_name = request.spec.project.repository_name

    pyproject = next(f for f in request.rendered.files if f.target == "pyproject.toml")
    text = pyproject.content.decode("utf-8")

    assert f"{repository_name} = " in text
    assert repository_name == "credit-risk-utils"


def _string_comparators(path: Path) -> set[str]:
    """Every string literal a file compares (`==`/`!=`/`in`/...) against."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    literals: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        for operand in (node.left, *node.comparators):
            if isinstance(operand, ast.Constant) and isinstance(operand.value, str):
                literals.add(operand.value)
    return literals


def test_no_shipped_module_hardcodes_a_discovered_component_id() -> None:
    """CF-08.03 (ADR 0019): the regression guard for the branch this review
    generalised. `pipeline._resolved_component_options` used to compare
    `archetype != "library"` directly; the fix reads the selected
    archetype's own discovered descriptor instead. This walks every scanned
    module's comparisons and fails if any of them tests equality against a
    real, currently-discovered component id -- so a future archetype-specific
    branch regresses loudly, not silently.
    """
    component_ids = {d.id for d in engine.discover()}
    assert component_ids, "the installed catalogue must be non-empty for this guard"

    for module_name in _SCANNED_MODULES:
        path = SRC_ROOT / f"{module_name}.py"
        hardcoded = _string_comparators(path) & component_ids
        assert not hardcoded, (
            f"{path.name} compares against hardcoded component id(s) "
            f"{sorted(hardcoded)} -- component identity must come from "
            "discovery (CF-08.03, ADR 0019), not a literal."
        )
