"""Tests for scripts/labels.py against the real .github/labels.toml manifest.

`scripts` is on `pythonpath` (see `[tool.pytest.ini_options]` in
pyproject.toml), so this imports the module directly -- matching the pattern
`test_adr.py` uses for `adr` and `test_cli.py` uses for `create_forge.cli`.

These validate the manifest's *shape* only -- colour format, description
length, no accidental name collisions. They do not talk to GitHub; the plan
and apply logic in labels.py is exercised by hand against the real repos (see
CONTRIBUTING.md's Labels section), the same way scripts/adr.py's checks are
unit-tested here while the ADRs themselves are reviewed by a human.
"""

from __future__ import annotations

import re

from labels import (
    _MAX_DESCRIPTION_LENGTH,
    _MAX_NAME_LENGTH,
    MANIFEST_FILE,
    LabelSpec,
    build_plan,
    desired_labels,
    load_manifest,
)

_HEX_COLOR_RE = re.compile(r"^[0-9a-f]{6}$")
_GROUP_LABEL_RE = re.compile(r"^[a-z]+:[a-z][a-z0-9]*(-[a-z0-9]+)*$")

_manifest = load_manifest(MANIFEST_FILE)
_labels = desired_labels(_manifest)


def test_manifest_loads() -> None:
    assert "groups" in _manifest
    assert len(_manifest["groups"]) > 0


def test_no_name_collisions_across_groups() -> None:
    """desired_labels() collapses duplicates into a dict -- catch that here."""
    raw_count = sum(
        len(group.get("labels", {})) for group in _manifest.get("groups", {}).values()
    ) + len(_manifest.get("unprefixed", {}))
    assert len(_labels) == raw_count


def test_every_color_is_a_bare_six_digit_hex() -> None:
    for name, spec in _labels.items():
        assert _HEX_COLOR_RE.match(spec.color), (
            f"{name}: color {spec.color!r} must be six lowercase hex digits, no '#'"
        )


def test_every_description_is_present_and_within_githubs_limit() -> None:
    for name, spec in _labels.items():
        assert spec.description, f"{name}: description must not be empty"
        assert len(spec.description) <= _MAX_DESCRIPTION_LENGTH, (
            f"{name}: description is {len(spec.description)} chars, "
            f"GitHub's limit is {_MAX_DESCRIPTION_LENGTH}"
        )


def test_every_name_is_within_githubs_length_limit() -> None:
    for name in _labels:
        assert len(name) <= _MAX_NAME_LENGTH, (
            f"{name}: exceeds GitHub's name length limit"
        )


def test_group_labels_are_lowercase_kebab_case() -> None:
    """Unprefixed entries ("good first issue") are exempt -- they intentionally
    keep GitHub's stock spelling, spaces included.
    """
    unprefixed = set(_manifest.get("unprefixed", {}))
    for name in _labels:
        if name in unprefixed:
            continue
        assert _GROUP_LABEL_RE.match(name), (
            f"{name}: must be '<group>:<kebab-case-label>'"
        )


def test_each_groups_colors_are_distinct() -> None:
    """A group whose shades collide is a copy-paste slip, invisible in review."""
    for group_name, group in _manifest.get("groups", {}).items():
        colors = [spec["color"] for spec in group.get("labels", {}).values()]
        assert len(colors) == len(set(colors)), (
            f"{group_name}: duplicate colour within group"
        )


def test_build_plan_creates_everything_against_an_empty_repo() -> None:
    plan = build_plan(_labels, current={}, prune=True)
    assert set(plan.creates) == set(_labels)
    assert plan.updates == {}
    assert plan.unchanged == ()
    assert plan.prunes == ()


def test_build_plan_reports_unchanged_when_current_matches() -> None:
    plan = build_plan(_labels, current=dict(_labels), prune=False)
    assert plan.creates == {}
    assert plan.updates == {}
    assert set(plan.unchanged) == set(_labels)
    assert plan.prunes == ()


def test_build_plan_detects_an_update() -> None:
    name, spec = next(iter(_labels.items()))
    stale = {name: LabelSpec(color="ffffff", description=spec.description)}
    plan = build_plan(_labels, current=stale, prune=False)
    assert name in plan.updates
    assert plan.updates[name] == spec


def test_build_plan_only_prunes_when_asked() -> None:
    current = {**_labels, "stock-label": LabelSpec(color="000000", description="old")}
    without_prune = build_plan(_labels, current=current, prune=False)
    assert without_prune.prunes == ()

    with_prune = build_plan(_labels, current=current, prune=True)
    assert with_prune.prunes == ("stock-label",)


def test_good_first_issue_and_help_wanted_stay_unprefixed() -> None:
    """The one deliberate exception to the "<group>:<label>" scheme."""
    assert "good first issue" in _labels
    assert "help wanted" in _labels
