"""Tests for scripts/check_workflows.py against the real .github/workflows/ set.

`scripts` is on `pythonpath` (see `[tool.pytest.ini_options]` in
pyproject.toml), so this imports the checker directly rather than via
subprocess -- matching `tests/test_adr.py`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from check_workflows import (
    WORKFLOW_DIR,
    check_all,
    check_declares_permissions,
    check_permission_placement,
    check_pinned_references,
    check_runner_labels,
    discover,
)

_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASELINE_CONTRACT = _REPO_ROOT / "docs" / "ci-runner-baseline.md"
_REUSABLE = "./.github/workflows/linux-checks.yml"


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_real_workflows_have_no_errors() -> None:
    """The actual .github/workflows/ set must pass every check -- CI enforces this."""
    assert check_all() == []


def test_discover_finds_real_workflows() -> None:
    names = {p.name for p in discover(WORKFLOW_DIR)}
    assert {
        "ci.yml",
        "docs.yml",
        "release.yml",
        "linux-checks.yml",
        "runner-canary.yml",
    } <= names


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


def test_runner_labels_pass_on_real_set() -> None:
    assert check_runner_labels(discover(WORKFLOW_DIR)) == []


def test_runner_labels_flag_ubuntu_latest(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml",
        "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps: []\n",
    )
    errors = check_runner_labels([workflow])
    assert any("job 'a'" in e and "'ubuntu-latest'" in e for e in errors)


def test_runner_labels_flag_ubuntu_latest_in_a_list_and_a_mapping(
    tmp_path: Path,
) -> None:
    workflow = _write(
        tmp_path / "w.yml",
        "jobs:\n"
        "  a:\n    runs-on: [self-hosted, ubuntu-latest]\n"
        "  b:\n    runs-on:\n      labels: ubuntu-latest\n",
    )
    errors = check_runner_labels([workflow])
    assert len(errors) == 2


def test_runner_labels_flag_ubuntu_latest_handed_to_a_reusable_workflow(
    tmp_path: Path,
) -> None:
    workflow = _write(
        tmp_path / "w.yml",
        f"jobs:\n  linux:\n    uses: {_REUSABLE}\n    with:\n"
        "      runner: ubuntu-latest\n",
    )
    assert any("'ubuntu-latest'" in e for e in check_runner_labels([workflow]))


def test_runner_labels_accept_explicit_images_and_expressions(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / "w.yml",
        "jobs:\n"
        "  a:\n    runs-on: ubuntu-24.04\n"
        "  b:\n    runs-on: ${{ inputs.runner }}\n"
        "  c:\n    runs-on: windows-latest\n",
    )
    assert check_runner_labels([workflow]) == []


def _workflow(name: str) -> dict[Any, Any]:
    """A real workflow, parsed. Keyed by `Any` because PyYAML reads a bare `on:`
    as the boolean `True`.
    """
    data = yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{name} did not parse to a mapping"
    return data


def _contract_label(role: str) -> str:
    """The label `docs/ci-runner-baseline.md` records for a `Baseline`/`Canary` row."""
    text = _BASELINE_CONTRACT.read_text(encoding="utf-8")
    match = re.search(rf"^\| {role} \| `([^`]+)` \|", text, re.MULTILINE)
    assert match, f"docs/ci-runner-baseline.md has no `{role}` row naming a label"
    return match.group(1)


def test_protected_ubuntu_jobs_run_on_the_contract_baseline() -> None:
    """Every Ubuntu job outside the canary runs on the label the contract
    records, so a promotion that edits only the workflows -- or only the
    document -- fails here rather than silently disagreeing.
    """
    baseline = _contract_label("Baseline")

    ci_jobs = _workflow("ci.yml")["jobs"]
    assert ci_jobs["linux"]["uses"] == _REUSABLE
    assert ci_jobs["linux"]["with"] == {"runner": baseline}
    assert ci_jobs["all-green"]["runs-on"] == baseline

    for name in ("docs.yml", "release.yml"):
        for job_name, job in _workflow(name)["jobs"].items():
            assert job["runs-on"] == baseline, f"{name}: {job_name}"


def test_canary_runs_the_same_checks_on_the_contract_canary_label() -> None:
    canary = _contract_label("Canary")
    assert canary != _contract_label("Baseline"), "the canary must be a different image"

    jobs = _workflow("runner-canary.yml")["jobs"]
    assert list(jobs) == ["canary"]
    assert jobs["canary"]["uses"] == _REUSABLE
    assert jobs["canary"]["with"] == {"runner": canary}


def test_canary_cannot_gate_a_merge() -> None:
    """The canary lives in its own workflow, is not a `needs` of the required
    aggregate, and no job it runs can carry the required check's name.
    """
    ci = _workflow("ci.yml")
    assert "linux" in ci["jobs"]["all-green"]["needs"]
    assert ci["jobs"]["all-green"]["name"] == "All checks passed"

    canary = _workflow("runner-canary.yml")
    assert not any(
        "All checks passed" in str(j.get("name")) for j in canary["jobs"].values()
    )
    called = _workflow("linux-checks.yml")["jobs"]
    assert not any(j.get("name") == "All checks passed" for j in called.values())


def test_reusable_linux_workflow_takes_its_runner_from_the_caller() -> None:
    workflow = _workflow("linux-checks.yml")
    trigger = workflow[True]  # the bare `on:` key
    assert set(trigger) == {"workflow_call"}
    assert trigger["workflow_call"]["inputs"]["runner"]["required"] is True
    for name, job in workflow["jobs"].items():
        assert job["runs-on"] == "${{ inputs.runner }}", name
    assert workflow["permissions"] == {"contents": "read"}


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
