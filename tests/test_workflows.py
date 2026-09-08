"""Tests for scripts/check_workflows.py against the real .github/workflows/ set.

`scripts` is on `pythonpath` (see `[tool.pytest.ini_options]` in
pyproject.toml), so this imports the checker directly rather than via
subprocess -- matching `tests/test_adr.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

from check_workflows import (
    WORKFLOW_DIR,
    check_all,
    check_declares_permissions,
    check_permission_placement,
    check_pinned_references,
    discover,
)

_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_real_workflows_have_no_errors() -> None:
    """The actual .github/workflows/ set must pass every check -- CI enforces this."""
    assert check_all() == []


def test_discover_finds_real_workflows() -> None:
    names = {p.name for p in discover(WORKFLOW_DIR)}
    assert {"ci.yml", "docs.yml", "release.yml"} <= names


def test_discover_includes_yaml_extension(tmp_path: Path) -> None:
    _write(tmp_path / "a.yml", "permissions: {}\n")
    _write(tmp_path / "b.yaml", "permissions: {}\n")
    _write(tmp_path / "notes.md", "ignored\n")
    assert [p.name for p in discover(tmp_path)] == ["a.yml", "b.yaml"]


def test_pinned_references_pass_on_real_set() -> None:
    assert check_pinned_references(discover(WORKFLOW_DIR)) == []


def test_pinned_references_accept_list_and_mapped_shapes(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml",
        "jobs:\n"
        "  a:\n"
        "    steps:\n"
        f"      - uses: actions/checkout@{_SHA} # v7.0.1\n"
        "      - name: Install uv\n"
        f"        uses: astral-sh/setup-uv@{_SHA} # v7.6.0\n",
    )
    assert check_pinned_references([workflow]) == []


def test_pinned_references_flag_floating_tag(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", "    - uses: actions/checkout@v7\n")
    errors = check_pinned_references([workflow])
    assert any("mutable ref" in e and "'v7'" in e for e in errors)


def test_pinned_references_flag_semver_tag(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml", "    - uses: pypa/gh-action-pypi-publish@v1.14.2\n"
    )
    errors = check_pinned_references([workflow])
    assert any("mutable ref" in e for e in errors)


def test_pinned_references_flag_branch(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", "    - uses: actions/checkout@main\n")
    errors = check_pinned_references([workflow])
    assert any("mutable ref" in e for e in errors)


def test_pinned_references_flag_abbreviated_sha(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml", f"    - uses: actions/checkout@{_SHA[:12]} # v7.0.1\n"
    )
    errors = check_pinned_references([workflow])
    assert any("not a full 40-character lowercase commit SHA" in e for e in errors)


def test_pinned_references_flag_uppercase_sha(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml", f"    - uses: actions/checkout@{_SHA.upper()} # v7.0.1\n"
    )
    errors = check_pinned_references([workflow])
    assert any("not a full 40-character lowercase commit SHA" in e for e in errors)


def test_pinned_references_flag_missing_version_comment(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", f"    - uses: actions/checkout@{_SHA}\n")
    errors = check_pinned_references([workflow])
    assert any("no adjacent '# <version>' comment" in e for e in errors)


def test_pinned_references_allow_local_and_docker(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml",
        "    - uses: ./.github/actions/local\n    - uses: docker://alpine:3.20\n",
    )
    assert check_pinned_references([workflow]) == []


def test_declares_permissions_passes_on_real_set() -> None:
    assert check_declares_permissions(discover(WORKFLOW_DIR)) == []


def test_declares_permissions_flags_missing_key(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", "on: push\njobs: {}\n")
    errors = check_declares_permissions([workflow])
    assert any("no top-level 'permissions:' key" in e for e in errors)


def test_declares_permissions_accepts_empty_mapping(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", "permissions: {}\njobs: {}\n")
    assert check_declares_permissions([workflow]) == []


def test_permission_placement_passes_on_real_set() -> None:
    assert check_permission_placement(discover(WORKFLOW_DIR)) == []


def test_permission_placement_flags_workflow_level_write(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", "permissions:\n  contents: write\njobs: {}\n")
    errors = check_permission_placement([workflow])
    assert any("'contents: write' at the workflow level" in e for e in errors)


def test_permission_placement_flags_workflow_level_write_all(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", "permissions: write-all\njobs: {}\n")
    errors = check_permission_placement([workflow])
    assert any("write-all" in e for e in errors)


def test_permission_placement_allows_job_level_write(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml",
        "permissions: {}\njobs:\n  release:\n    permissions:\n      contents: write\n",
    )
    assert check_permission_placement([workflow]) == []


def test_permission_placement_allows_workflow_level_read(tmp_path: Path) -> None:
    workflow = _write(tmp_path / "w.yml", "permissions:\n  contents: read\njobs: {}\n")
    assert check_permission_placement([workflow]) == []


def test_workflow_security_contract_is_linked_from_entry_points() -> None:
    """The canonical contract must be reachable from the top-level docs."""
    link_re = re.compile(r"\([^)]*workflow-security\.md[^)]*\)")
    for name in ("CLAUDE.md", "CONTRIBUTING.md", "SECURITY.md"):
        text = (_REPO_ROOT / name).read_text(encoding="utf-8")
        assert link_re.search(text), f"{name} does not link workflow-security.md"


def test_adr_0037_is_linked_from_entry_points() -> None:
    link_re = re.compile(r"\([^)]*0037-immutable-workflow-actions\.md[^)]*\)")
    for name in ("CLAUDE.md", "CONTRIBUTING.md", "SECURITY.md", "docs/adr/README.md"):
        text = (_REPO_ROOT / name).read_text(encoding="utf-8")
        assert link_re.search(text), f"{name} does not link ADR 0037"
