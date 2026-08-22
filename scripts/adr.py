"""Checks that the `docs/adr/` Architecture Decision Record set stays
internally consistent.

ADRs are written once and never edited (ADR 0001), so nothing re-derives their
content -- but the *set* of them can still drift: a record added without
updating the index, a gap left by a rename, a missing heading. Both CI and
``uv run poe check`` (via ``tests/test_adr.py``) run these checks; ``poe
check:adr`` runs them standalone.

Trimmed from forge-template's ``src/forge_template/adr.py`` -- ported rather
than imported across repos, per issue #6.
"""  # noqa: D205

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = REPO_ROOT / "docs" / "adr"
INDEX_FILE = ADR_DIR / "README.md"

_FILENAME_RE = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
_HEADING_RE = re.compile(r"^#\s+(\d+)\.\s+\S")
_REQUIRED_HEADINGS = ("## Status", "## Context", "## Decision", "## Consequences")
# Matches the ADR's own filename inside a Markdown link, e.g.
# "[0002 -- Foo](0002-foo.md)" or "(0002-foo.md#anchor)".
_INDEX_LINK_RE = re.compile(r"\((\d{4}-[a-z0-9-]+\.md)(?:#[^)]*)?\)")


def discover(adr_dir: Path = ADR_DIR) -> list[Path]:
    """Return every ADR record file, sorted, excluding the index itself."""
    return sorted(p for p in adr_dir.glob("*.md") if p.name != "README.md")


def check_filenames(paths: list[Path]) -> list[str]:
    """Every record filename must be `NNNN-slug.md`."""
    errors = []
    for path in paths:
        if not _FILENAME_RE.match(path.name):
            errors.append(f"{path.name}: filename must match NNNN-slug.md")
    return errors


def check_numbering(paths: list[Path]) -> list[str]:
    """Record numbers must be contiguous from 0001, with no gaps or duplicates."""
    errors = []
    numbers = []
    for path in paths:
        match = _FILENAME_RE.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    seen: set[int] = set()
    for n in numbers:
        if n in seen:
            errors.append(f"{n:04d}: duplicate ADR number")
        seen.add(n)
    expected = list(range(1, len(seen) + 1))
    if sorted(seen) != expected:
        errors.append(
            f"ADR numbers must be contiguous from 0001; got {sorted(seen)}, "
            f"expected {expected}"
        )
    return errors


def check_indexed(paths: list[Path], index_file: Path = INDEX_FILE) -> list[str]:
    """Every record must be linked from the index, and every link in the
    index must resolve to a real record file.
    """  # noqa: D205
    errors = []
    if not index_file.exists():
        return [f"{index_file}: ADR index file is missing"]

    index_text = index_file.read_text(encoding="utf-8")
    linked = set(_INDEX_LINK_RE.findall(index_text))
    on_disk = {path.name for path in paths}

    for name in sorted(on_disk - linked):
        errors.append(f"{name}: not linked from {index_file.name}")
    for name in sorted(linked - on_disk):
        errors.append(f"{index_file.name}: links to {name}, which does not exist")
    return errors


def check_headings(paths: list[Path]) -> list[str]:
    """Every record needs an `# N. Title` heading matching its filename
    number, plus all four Nygard section headings.
    """  # noqa: D205
    errors = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        match = _FILENAME_RE.match(path.name)
        expected_number = int(match.group(1)) if match else None

        title_line = next((line for line in lines if line.startswith("# ")), None)
        if title_line is None:
            errors.append(f"{path.name}: missing '# N. Title' heading")
        else:
            heading_match = _HEADING_RE.match(title_line)
            if heading_match is None:
                errors.append(
                    f"{path.name}: title heading must match '# N. Title', "
                    f"got {title_line!r}"
                )
            elif (
                expected_number is not None
                and int(heading_match.group(1)) != expected_number
            ):
                errors.append(
                    f"{path.name}: title heading number "
                    f"{heading_match.group(1)} does not match filename "
                    f"number {expected_number:04d}"
                )

        for heading in _REQUIRED_HEADINGS:
            if heading not in lines:
                errors.append(f"{path.name}: missing '{heading}' heading")
    return errors


def check_all(adr_dir: Path = ADR_DIR, index_file: Path = INDEX_FILE) -> list[str]:
    """Run every check and return the combined list of errors."""
    paths = discover(adr_dir)
    return [
        *check_filenames(paths),
        *check_numbering(paths),
        *check_indexed(paths, index_file),
        *check_headings(paths),
    ]


def main() -> int:
    """Print any failures and return a process exit code."""
    errors = check_all()
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} ADR check(s) failed.", file=sys.stderr)
        return 1
    print("ok: docs/adr/ is internally consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
