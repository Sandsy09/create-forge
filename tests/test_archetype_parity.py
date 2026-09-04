"""CF-08.03's archetype-parity review, made executable (ADR 0019).

Verifies, against the real installed `forge-template` engine (the `engine`
extra, present when `uv sync --all-extras` was used -- see
`tests/test_engine_adapter.py`'s own docstring), that `create-forge` remains
generic across the Library and CLI Application archetypes rather than
special-casing either one:

- every discovered archetype builds a structurally identical ProjectSpec
  payload and runs through one `build_generation_request` pipeline, with its
  own discovered required capabilities and no archetype-specific branch --
  CF-13.05 generalised this from the hardcoded Library/CLI pair to the whole
  discovered catalogue, which now also covers Data Science;
- component compatibility and discovery stay engine-owned -- see
  `tests/test_engine_adapter.py::test_discover_preserves_public_component_descriptors`
  for the deeper proof that descriptors pass through unchanged;
- `cli`'s discovered descriptor declares no options, and create-forge sends
  it none;
- no `command_name` field exists anywhere in this repository, and a `cli`
  render's console command is exactly `ProjectSpec.project.repository_name`;
- no shipped module hardcodes a component id in *any* position -- CF-13.05
  widened this guard from comparison operands alone (CF-08.03's original
  form, catching the branch generalised in
  `pipeline._resolved_component_options`) to every string literal, closing
  the dict-key, membership-constant, and `match`/`case` forms an
  archetype-specific special case would otherwise take.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from create_forge import engine, pipeline
from create_forge.pipeline import Catalogue
from create_forge.spec import SelectionKind, SelectionRequest, build_spec_payload

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


def _archetype_selections() -> list[tuple[str, tuple[str, ...]]]:
    """Every discovered archetype paired with its own discovered required
    capabilities.

    CF-13.05: the parity tests below parametrise over this rather than a
    hardcoded `("library", "cli")` tuple, so a new archetype (Data Science,
    which requires `jupyter`) is covered automatically and no requirement id
    is written down here -- `Catalogue.required_ids` reads it off the
    descriptor.
    """
    catalogue = Catalogue(tuple(engine.discover()))
    return [
        (
            descriptor.id,
            catalogue.required_ids(descriptor.id, SelectionKind.CAPABILITIES),
        )
        for descriptor in catalogue.archetypes
    ]


@pytest.mark.parametrize(
    ("archetype", "required_capabilities"), _archetype_selections()
)
def test_every_archetype_builds_the_same_projectspec_shape(
    archetype: str, required_capabilities: tuple[str, ...]
) -> None:
    """Criterion 3: one generic construction path. The only differences
    between any two archetype payloads are the archetype id, its discovered
    required capabilities, and `component_options` -- every other section
    (`project`, `python`) is produced by the exact same code, unaware which
    archetype it is building for.
    """
    reference = build_spec_payload(_VALID_ANSWERS, archetype="library")
    payload = build_spec_payload(
        _VALID_ANSWERS,
        archetype=archetype,
        capabilities=required_capabilities,
    )

    for key in ("protocol_version", "project", "python"):
        assert payload[key] == reference[key]

    assert payload["components"] == {
        "archetype": archetype,
        "capabilities": list(required_capabilities),
        "platforms": [],
    }


@pytest.mark.parametrize(
    ("archetype", "required_capabilities"), _archetype_selections()
)
def test_every_archetype_renders_through_the_one_shared_pipeline(
    archetype: str, required_capabilities: tuple[str, ...]
) -> None:
    """Criterion 3, end to end: `build_generation_request` is not
    archetype-branched -- every call below runs the identical function, with
    the archetype's own discovered requirements satisfied.
    """
    request = pipeline.build_generation_request(
        _VALID_ANSWERS,
        selection=SelectionRequest.of(
            archetype=archetype, capabilities=required_capabilities
        ),
    )
    assert request.spec.components.archetype == archetype
    assert tuple(request.spec.components.capabilities) == required_capabilities
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


def _string_literals(path: Path) -> set[str]:
    """Every `str` constant a file contains, in any AST position.

    CF-13.05 widened this from `ast.Compare` operands alone (CF-08.03's
    original form) to every `ast.Constant`, so a component id used as a dict
    key, a `match`/`case` pattern, a set membership constant, or a
    `.startswith` argument is caught too -- those are the forms an
    archetype-specific special case takes once `==` is off the table.
    Docstrings and f-string fragments are `ast.Constant` too but never equal
    a bare component id, so they cost nothing here.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_no_shipped_module_hardcodes_a_discovered_component_id() -> None:
    """CF-08.03 (ADR 0019), widened by CF-13.05 (ADR 0030): the regression
    guard for the branch this review generalised.
    `pipeline._resolved_component_options` used to compare
    `archetype != "library"` directly; the fix reads the selected
    archetype's own discovered descriptor instead. This walks every scanned
    module's string literals and fails if any of them is a real,
    currently-discovered component id -- so a future archetype-specific
    branch regresses loudly, not silently, whatever syntax it uses.
    """
    component_ids = {d.id for d in engine.discover()}
    assert component_ids, "the installed catalogue must be non-empty for this guard"

    for module_name in _SCANNED_MODULES:
        path = SRC_ROOT / f"{module_name}.py"
        hardcoded = _string_literals(path) & component_ids
        assert not hardcoded, (
            f"{path.name} contains hardcoded component id(s) "
            f"{sorted(hardcoded)} -- component identity must come from "
            "discovery (CF-08.03, ADR 0019; CF-13.05, ADR 0030), not a literal."
        )
