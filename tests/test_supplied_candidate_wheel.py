"""`CREATE_FORGE_CANDIDATE_WHEEL` (CF-21.03, ADR 0056): the opt-in that points the
installed suites at an already-built wheel -- the one PyPI serves -- instead of
building the working tree.

The override is only worth having if it cannot quietly test the wrong thing, so
the cases below are the ways it could: an unset variable must change nothing, and
a path that is missing, is not a wheel, or is a wheel for another version must
fail loudly rather than fall back to a build.

No network, no build.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.installed_client import (
    CLIENT_VERSION,
    SUPPLIED_WHEEL_ENV,
    supplied_candidate_wheel,
)

if TYPE_CHECKING:
    from pathlib import Path


def _wheel(root: Path, version: str = CLIENT_VERSION) -> Path:
    path = root / f"create_forge-{version}-py3-none-any.whl"
    path.write_bytes(b"not really a wheel; the helper only checks the name")
    return path


def test_unset_or_empty_means_build_from_the_working_tree() -> None:
    assert supplied_candidate_wheel({}) is None
    assert supplied_candidate_wheel({SUPPLIED_WHEEL_ENV: ""}) is None


def test_a_matching_wheel_is_returned_as_given(tmp_path: Path) -> None:
    wheel = _wheel(tmp_path)

    assert supplied_candidate_wheel({SUPPLIED_WHEEL_ENV: str(wheel)}) == wheel


def test_a_missing_file_fails_instead_of_falling_back_to_a_build(
    tmp_path: Path,
) -> None:
    missing = tmp_path / f"create_forge-{CLIENT_VERSION}-py3-none-any.whl"

    with pytest.raises(ValueError, match=r"not an existing \.whl file"):
        supplied_candidate_wheel({SUPPLIED_WHEEL_ENV: str(missing)})


def test_a_directory_or_an_sdist_is_not_a_wheel(tmp_path: Path) -> None:
    sdist = tmp_path / f"create_forge-{CLIENT_VERSION}.tar.gz"
    sdist.write_bytes(b"")

    for bad in (tmp_path, sdist):
        with pytest.raises(ValueError, match=r"not an existing \.whl file"):
            supplied_candidate_wheel({SUPPLIED_WHEEL_ENV: str(bad)})


def test_a_wheel_for_another_version_is_refused(tmp_path: Path) -> None:
    other = _wheel(tmp_path, version="0.0.1")

    with pytest.raises(ValueError, match=f"create_forge-{CLIENT_VERSION}-"):
        supplied_candidate_wheel({SUPPLIED_WHEEL_ENV: str(other)})
