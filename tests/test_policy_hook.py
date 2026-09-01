"""The downstream policy-consumption seam (CF-09.01, ADR 0022).

No engine import here -- `spec.SelectionRequest`/`SelectionProvenance` must
stay importable and testable without the optional `engine` extra (ADR 0018)
installed, exactly like `spec.py`'s other exports. The real round trip
through `forge_template.parse_project_spec`/`validate_project_spec` is
`tests/test_engine_adapter.py::test_provenance_survives_parse_and_validate_canonicalised`'s
job instead.

See docs/organisation-policy-consumption.md for the contract these tests
characterize.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from create_forge.spec import (
    SelectionKind,
    SelectionProvenance,
    SelectionRequest,
    build_spec_payload,
)

# -- SelectionRequest.of: absent vs. explicit-and-empty ----------------------


def test_omitted_capabilities_and_platforms_are_not_explicit() -> None:
    """Protocol v1: an absent selection kind permits a policy default."""
    selection = SelectionRequest.of(archetype="library")

    assert selection.capabilities == ()
    assert selection.platforms == ()
    assert selection.explicit == {SelectionKind.ARCHETYPE}


def test_explicit_empty_list_is_still_explicit() -> None:
    """Protocol v1: "An explicitly empty list is still an explicit choice" --
    the exact distinction `ProjectSpec` itself cannot reconstruct, which is
    the reason this type exists at all.
    """
    selection = SelectionRequest.of(archetype="library", capabilities=[], platforms=[])

    assert selection.capabilities == ()
    assert selection.platforms == ()
    assert selection.explicit == {
        SelectionKind.ARCHETYPE,
        SelectionKind.CAPABILITIES,
        SelectionKind.PLATFORMS,
    }


def test_a_supplied_non_empty_list_is_explicit_and_preserved() -> None:
    selection = SelectionRequest.of(
        archetype="library", capabilities=["documentation"], platforms=["github"]
    )

    assert selection.capabilities == ("documentation",)
    assert selection.platforms == ("github",)
    assert SelectionKind.CAPABILITIES in selection.explicit
    assert SelectionKind.PLATFORMS in selection.explicit


def test_archetype_explicit_defaults_true_but_can_be_marked_absent() -> None:
    """`archetype` has no absent *form* -- ProjectSpec always selects exactly
    one -- but a caller (`cli.py`'s prompt-skipped-to-one-choice case) can
    still mark the choice as not explicit, e.g. because a policy default
    should be allowed to have applied instead.
    """
    default_explicit = SelectionRequest.of(archetype="library")
    assert SelectionKind.ARCHETYPE in default_explicit.explicit

    not_explicit = SelectionRequest.of(archetype="library", archetype_explicit=False)
    assert SelectionKind.ARCHETYPE not in not_explicit.explicit


def test_both_kinds_reach_build_spec_payload_as_the_effective_selection() -> None:
    """`explicit` is consumption-side bookkeeping only -- it never reaches the
    wire payload itself. Only the *effective* selection does, exactly as
    `build_spec_payload`'s existing `capabilities`/`platforms` parameters
    already behaved before this seam existed.
    """
    selection = SelectionRequest.of(
        archetype="library", capabilities=["documentation"], platforms=[]
    )

    payload = build_spec_payload(
        {},
        archetype=selection.archetype,
        capabilities=selection.capabilities,
        platforms=selection.platforms,
    )

    components = cast("dict[str, object]", payload["components"])
    assert components == {
        "archetype": "library",
        "capabilities": ["documentation"],
        "platforms": [],
    }
    assert "explicit" not in components


# -- SelectionProvenance: emitted only when non-empty, never a document ------


def test_no_provenance_omits_the_field() -> None:
    payload = build_spec_payload({}, archetype="library")

    assert "provenance" not in payload


def test_empty_provenance_omits_the_field() -> None:
    """A caller can pass a `SelectionProvenance` instance and still get
    nothing on the wire -- `is_empty()` gates emission, not mere presence of
    the keyword, matching `component_options`'s existing omit-when-empty rule.
    """
    payload = build_spec_payload(
        {}, archetype="library", provenance=SelectionProvenance()
    )

    assert "provenance" not in payload


def test_provenance_with_policies_is_emitted_as_identifiers_only() -> None:
    payload = build_spec_payload(
        {},
        archetype="library",
        provenance=SelectionProvenance(
            profile="acme-defaults", policies=("org-baseline", "security-required")
        ),
    )

    assert payload["provenance"] == {
        "profile": "acme-defaults",
        "policies": ["org-baseline", "security-required"],
    }


# -- Containment guard: the seam cannot smuggle more than identifiers --------


def test_selection_request_carries_no_field_beyond_the_permitted_set() -> None:
    """CF-09.01's criterion 3: prevent policy from becoming an arbitrary file
    or code-execution overlay. A future field added to `SelectionRequest` --
    a path, file content, a component option, a callable hook -- fails this
    test, not silently. `explicit` is bookkeeping, not part of the effective
    selection ProjectSpec itself receives.
    """
    field_names = {f.name for f in dataclasses.fields(SelectionRequest)}

    assert field_names == {"archetype", "capabilities", "platforms", "explicit"}


def test_selection_provenance_carries_no_field_beyond_the_permitted_set() -> None:
    """Mirrors `forge_template.SelectionProvenance`'s own field set exactly
    -- protocol v1 is explicit that provenance "neither embeds a policy
    document nor grants rendering authority", so there is no field here a
    policy document's content could ever populate.
    """
    field_names = {f.name for f in dataclasses.fields(SelectionProvenance)}

    assert field_names == {"profile", "policies"}


def test_selection_provenance_fields_are_identifiers_or_none_typed() -> None:
    """A cruder but language-level version of the same guard: every field's
    declared type is a bare string, a tuple of strings, or `str | None` --
    never `bytes`, `Path`, `Callable`, or anything that could carry file
    content or code.
    """
    permitted_types = {"str | None", "tuple[str, ...]"}
    for f in dataclasses.fields(SelectionProvenance):
        assert f.type in permitted_types, (
            f"SelectionProvenance.{f.name} has type {f.type!r}, outside the "
            f"permitted identifier-only shape {permitted_types}"
        )
