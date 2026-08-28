"""`spec.build_spec_payload` -- derivation, overrides, omission, and parity.

No engine import here: `spec.py` must stay importable and testable without
the `engine` dependency group installed, so these tests exercise only the
wire-payload shape, never `forge_template.ProjectSpec` itself. That real
parse is `tests/test_engine_adapter.py`'s job.
"""

from __future__ import annotations

from typing import cast

from create_forge.spec import build_spec_payload


def _project(payload: dict[str, object]) -> dict[str, object]:
    """Narrow `payload["project"]` from `object` for typed assertions below."""
    return cast("dict[str, object]", payload["project"])


def test_omits_project_fields_with_no_source_value() -> None:
    payload = build_spec_payload({}, archetype="library")

    assert payload["protocol_version"] == 1
    assert payload["project"] == {}
    assert "python" not in payload
    assert "component_options" not in payload


def test_derives_package_name_and_repository_name_from_project_name() -> None:
    payload = build_spec_payload(
        {"project_name": "Credit Risk Utils"}, archetype="library"
    )

    project = _project(payload)
    assert project["name"] == "Credit Risk Utils"
    assert project["package_name"] == "credit_risk_utils"
    assert project["repository_name"] == "credit-risk-utils"


def test_explicit_data_override_wins_over_derivation() -> None:
    payload = build_spec_payload(
        {
            "project_name": "Credit Risk Utils",
            "package_name": "risk_lib",
            "repo_name": "risk-lib",
        },
        archetype="library",
    )

    project = _project(payload)
    assert project["package_name"] == "risk_lib"
    assert project["repository_name"] == "risk-lib"


def test_package_name_derivation_collapses_and_trims_punctuation() -> None:
    payload = build_spec_payload(
        {"project_name": "  --Credit  Risk!! Utils--  "}, archetype="library"
    )

    assert _project(payload)["package_name"] == "credit_risk_utils"


def test_license_key_is_renamed_to_licence() -> None:
    payload = build_spec_payload(
        {"project_name": "X", "license": "mit"}, archetype="library"
    )

    project = _project(payload)
    assert project["licence"] == "mit"
    assert "license" not in project


def test_description_is_passed_through_even_when_blank() -> None:
    payload = build_spec_payload(
        {"project_name": "X", "project_description": ""}, archetype="library"
    )

    assert _project(payload)["description"] == ""


def test_no_description_answer_omits_the_field() -> None:
    payload = build_spec_payload({"project_name": "X"}, archetype="library")

    assert "description" not in _project(payload)


def test_author_name_and_email_become_one_author() -> None:
    payload = build_spec_payload(
        {
            "project_name": "X",
            "author_name": "Test User",
            "author_email": "test@example.invalid",
        },
        archetype="library",
    )

    assert _project(payload)["authors"] == [
        {"name": "Test User", "email": "test@example.invalid"}
    ]


def test_author_name_alone_omits_email() -> None:
    payload = build_spec_payload(
        {"project_name": "X", "author_name": "Test User"}, archetype="library"
    )

    assert _project(payload)["authors"] == [{"name": "Test User"}]


def test_author_email_without_a_name_is_dropped() -> None:
    """An Author requires a name; a lone email cannot form a valid entry."""
    payload = build_spec_payload(
        {"project_name": "X", "author_email": "test@example.invalid"},
        archetype="library",
    )

    assert "authors" not in _project(payload)


def test_python_selection_requires_both_bounds() -> None:
    payload = build_spec_payload(
        {"project_name": "X", "python_min_version": "3.11"}, archetype="library"
    )

    assert "python" not in payload


def test_python_selection_present_when_both_bounds_given() -> None:
    payload = build_spec_payload(
        {
            "project_name": "X",
            "python_min_version": "3.11",
            "python_version": "3.13",
        },
        archetype="library",
    )

    assert payload["python"] == {"minimum": "3.11", "development": "3.13"}


def test_components_reflect_caller_supplied_selection_only() -> None:
    payload = build_spec_payload(
        {},
        archetype="library",
        capabilities=["changelog", "documentation"],
        platforms=["github"],
    )

    assert payload["components"] == {
        "archetype": "library",
        "capabilities": ["changelog", "documentation"],
        "platforms": ["github"],
    }


def test_component_options_are_copied_per_component() -> None:
    payload = build_spec_payload(
        {},
        archetype="library",
        component_options={"library": {"build_backend": "uv_build"}},
    )

    assert payload["component_options"] == {"library": {"build_backend": "uv_build"}}


def test_no_component_options_omits_the_key() -> None:
    payload = build_spec_payload({}, archetype="library")

    assert "component_options" not in payload


def test_interactive_and_non_interactive_parity() -> None:
    """Equal answer mappings must produce an identical payload regardless of
    how the answers were collected -- the same convergence
    docs/cli-conventions.md's "Interactive and non-interactive parity"
    section requires of `ScaffoldRequest` construction.
    """
    interactive_answers = {
        "project_name": "Parity Check",
        "license": "mit",
        "author_name": "Test User",
    }
    non_interactive_answers = dict(interactive_answers)

    assert build_spec_payload(
        interactive_answers, archetype="library"
    ) == build_spec_payload(non_interactive_answers, archetype="library")
