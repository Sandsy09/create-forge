"""Tests for scripts/adr.py against the real docs/adr/ set.

`scripts` is on `pythonpath` (see `[tool.pytest.ini_options]` in
pyproject.toml), so this imports the checker directly rather than via
subprocess -- matching the pattern `test_cli.py` uses for `create_forge.cli`.
"""

from __future__ import annotations

from pathlib import Path

from adr import (
    ADR_DIR,
    check_all,
    check_filenames,
    check_headings,
    check_indexed,
    check_numbering,
    discover,
)


def test_real_adr_set_has_no_errors() -> None:
    """The actual docs/adr/ set must pass every check -- this is what CI runs."""
    assert check_all() == []


def test_discover_excludes_index() -> None:
    paths = discover(ADR_DIR)
    assert all(p.name != "README.md" for p in paths)
    assert len(paths) > 0


def test_check_filenames_passes_on_real_set() -> None:
    assert check_filenames(discover(ADR_DIR)) == []


def test_check_filenames_flags_bad_name(tmp_path: Path) -> None:
    bad = tmp_path / "0001-Title-Case.md"
    bad.write_text("x")
    errors = check_filenames([bad])
    assert len(errors) == 1
    assert "0001-Title-Case.md" in errors[0]


def test_check_filenames_flags_missing_number(tmp_path: Path) -> None:
    bad = tmp_path / "no-number-here.md"
    bad.write_text("x")
    errors = check_filenames([bad])
    assert len(errors) == 1


def test_check_numbering_passes_on_real_set() -> None:
    assert check_numbering(discover(ADR_DIR)) == []


def test_check_numbering_flags_gap(tmp_path: Path) -> None:
    for name in ("0001-first.md", "0003-third.md"):
        (tmp_path / name).write_text("x")
    errors = check_numbering(discover(tmp_path))
    assert any("contiguous" in e for e in errors)


def test_check_numbering_flags_duplicate(tmp_path: Path) -> None:
    (tmp_path / "0001-first.md").write_text("x")
    (tmp_path / "0001-first-again.md").write_text("x")
    errors = check_numbering(discover(tmp_path))
    assert any("duplicate" in e for e in errors)


def test_check_indexed_passes_on_real_set() -> None:
    assert check_indexed(discover(ADR_DIR)) == []


def test_check_indexed_flags_unlinked_record(tmp_path: Path) -> None:
    (tmp_path / "0001-first.md").write_text("x")
    index = tmp_path / "README.md"
    index.write_text("# ADRs\n\nNothing linked here.\n")
    errors = check_indexed(discover(tmp_path), index)
    assert any("0001-first.md" in e and "not linked" in e for e in errors)


def test_check_indexed_flags_broken_link(tmp_path: Path) -> None:
    (tmp_path / "0001-first.md").write_text("x")
    index = tmp_path / "README.md"
    index.write_text("- [0001](0001-first.md)\n- [0002](0002-missing.md)\n")
    errors = check_indexed(discover(tmp_path), index)
    assert any("0002-missing.md" in e and "does not exist" in e for e in errors)


def test_check_indexed_flags_missing_index_file(tmp_path: Path) -> None:
    (tmp_path / "0001-first.md").write_text("x")
    errors = check_indexed(discover(tmp_path), tmp_path / "README.md")
    assert any("missing" in e for e in errors)


def test_check_headings_passes_on_real_set() -> None:
    assert check_headings(discover(ADR_DIR)) == []


def test_check_headings_flags_missing_section(tmp_path: Path) -> None:
    bad = tmp_path / "0001-first.md"
    bad.write_text("# 1. First\n\n## Status\n\nAccepted\n\n## Context\n\nx\n")
    errors = check_headings([bad])
    assert any("## Decision" in e for e in errors)
    assert any("## Consequences" in e for e in errors)


def test_check_headings_flags_missing_title(tmp_path: Path) -> None:
    bad = tmp_path / "0001-first.md"
    bad.write_text("## Status\n\nAccepted\n")
    errors = check_headings([bad])
    assert any("missing '# N. Title'" in e for e in errors)


def test_check_headings_flags_number_mismatch(tmp_path: Path) -> None:
    bad = tmp_path / "0002-second.md"
    bad.write_text(
        "# 1. Wrong number\n\n"
        "## Status\n\nAccepted\n\n"
        "## Context\n\nx\n\n"
        "## Decision\n\nx\n\n"
        "## Consequences\n\nx\n"
    )
    errors = check_headings([bad])
    assert any("does not match filename number" in e for e in errors)
