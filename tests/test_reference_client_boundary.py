"""The reference-client dependency boundary (CF-09.03, ADR 0024).

These guards complement the behavioural client proof in
``tests/test_downstream_reference.py`` and forge-template's no-copy suite.
They exercise the two package-boundary facts that those tests cannot prove
from their own source: the supported engine has no reverse create-forge edge,
and the repository-only example does not become a shipped framework surface.
"""

from __future__ import annotations

import importlib.metadata
import re
import tomllib
from pathlib import Path

import forge_template
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
ADR = REPO_ROOT / "docs" / "adr" / "0024-reference-client-not-framework-dependency.md"

_CREATE_FORGE = canonicalize_name("create-forge")
_REVERSE_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+create_forge(?:\.|\s)|import\s+create_forge(?:\.|\s|$))",
    re.MULTILINE,
)


def test_supported_engine_declares_no_create_forge_dependency() -> None:
    """The installed compatibility-line engine cannot depend back on its client."""
    distribution = importlib.metadata.distribution("forge-template")
    declared = {
        canonicalize_name(Requirement(requirement).name)
        for requirement in distribution.requires or ()
    }

    assert _CREATE_FORGE not in declared


def test_supported_engine_imports_no_create_forge_module() -> None:
    """A missing metadata edge must not hide a source-level reverse import."""
    package_file = forge_template.__file__
    assert package_file is not None
    package_root = Path(package_file).resolve().parent

    offenders = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*.py")
        if _REVERSE_IMPORT_RE.search(path.read_text(encoding="utf-8"))
    ]

    assert not offenders, (
        f"forge-template imports create_forge from shipped source: {sorted(offenders)}"
    )


def test_downstream_reference_stays_out_of_distribution_artifacts() -> None:
    """The worked client is repository evidence, not a create-forge API."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    targets = data["tool"]["hatch"]["build"]["targets"]

    assert targets["wheel"]["packages"] == ["src/create_forge"]
    assert all(
        not include.removeprefix("./").startswith("examples/")
        for include in targets["sdist"]["include"]
    )


def test_reference_client_decision_is_linked_from_canonical_entry_points() -> None:
    """The final Stage 09 decision must remain discoverable."""
    assert ADR.is_file()
    link_re = re.compile(r"0024-reference-client-not-framework-dependency\.md")

    for relative_path in (
        "README.md",
        "CLAUDE.md",
        "CONTRIBUTING.md",
        "docs/integration-contract.md",
        "docs/downstream-client-reference.md",
    ):
        path = REPO_ROOT / relative_path
        assert link_re.search(path.read_text(encoding="utf-8")), (
            f"{relative_path} does not link ADR 0024"
        )
