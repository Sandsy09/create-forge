"""Guards keeping CF-04.01's engine-resolution documentation internally
consistent with the code -- the same "docs and code must not drift" idea as
`tests/test_adr.py` and `tests/test_drift.py`, applied to ADR 0011's rules
rather than to a Copier template.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
INTEGRATION_CONTRACT = REPO_ROOT / "docs" / "integration-contract.md"
ENGINE_RESOLUTION = REPO_ROOT / "docs" / "engine-resolution.md"
CLI_CONVENTIONS = REPO_ROOT / "docs" / "cli-conventions.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"

# PEP 503 normalisation: case-fold and collapse runs of -._ to a single "-".
_NORMALISE_RE = re.compile(r"[-_.]+")


def _normalise(name: str) -> str:
    return _NORMALISE_RE.sub("-", name).lower()


def _declared_dependency_names() -> set[str]:
    """Every top-level dependency name pyproject.toml declares, normalised.

    Reads `[project.dependencies]` only -- dependency-groups are dev-only
    tooling (ruff, pytest, ...) and never a runtime engine dependency.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    deps: list[str] = data["project"]["dependencies"]
    names = set()
    for spec in deps:
        # A requirement string's name is everything before the first
        # version/marker/extra delimiter.
        match = re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*", spec)
        if match:
            names.add(_normalise(match.group(0)))
    return names


def test_no_engine_dependency_means_no_assigned_range() -> None:
    """ADR 0011 and the integration contract say the first engine range must
    not be reserved speculatively -- only assigned once a real dependency
    exists and its compatibility tests pass. This is the executable form of
    that rule: the moment someone adds a `forge-template` dependency without
    updating the contract table, this must start failing.
    """
    engine_declared = "forge-template" in _declared_dependency_names()
    contract_text = INTEGRATION_CONTRACT.read_text(encoding="utf-8")

    assert not engine_declared, (
        "pyproject.toml now declares a forge-template dependency -- follow "
        "docs/engine-resolution.md's 'Assigning the first engine range' "
        "checklist, then update this test and the contract table together."
    )
    assert "| First engine line | Unassigned | Unassigned |" in contract_text, (
        "No forge-template dependency is declared yet, so "
        "docs/integration-contract.md's future row must stay unassigned."
    )


def test_engine_resolution_doc_is_linked_from_the_canonical_entry_points() -> None:
    """The living engine-resolution contract must stay discoverable from
    every doc that already names its sibling contracts (CLI conventions,
    cross-repository workflow) -- otherwise it is dead documentation nobody
    finds from the usual entry points.
    """
    link_re = re.compile(r"\([^)]*engine-resolution\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD, INTEGRATION_CONTRACT):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), f"{path.name} does not link engine-resolution.md"

    assert ENGINE_RESOLUTION.is_file()


def test_reserved_compatibility_exit_status_is_documented_once() -> None:
    """Exit status 3 is reserved by ADR 0011 for engine/protocol
    compatibility failures. It must appear in the CLI's exit-status table
    (docs/cli-conventions.md) and agree with the engine-resolution contract
    that it is reserved rather than already raised -- there is no code path
    under the v0.1.x direct-Copier line that can produce it yet.
    """
    conventions_text = CLI_CONVENTIONS.read_text(encoding="utf-8")
    resolution_text = ENGINE_RESOLUTION.read_text(encoding="utf-8")

    row_re = re.compile(r"^\|\s*`3`\s*\|.*\|\s*$", re.MULTILINE)
    row_match = row_re.search(conventions_text)
    assert row_match, "docs/cli-conventions.md has no exit-status row for `3`"
    assert "Reserved" in row_match.group(0)

    assert "exit status **`3`**, reserved exclusively for it" in resolution_text
