"""Guards keeping CF-04.01's engine-resolution documentation, CF-05.02's
engine-update policy, and CF-06.01/02's engine boundaries internally
consistent with the code -- the same "docs and code must not drift" idea as
`tests/test_adr.py` and `tests/test_drift.py`, applied to ADR 0011's, ADR
0012's, and ADR 0013's rules rather than to a Copier template.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
DEPENDABOT = REPO_ROOT / ".github" / "dependabot.yml"
INTEGRATION_CONTRACT = REPO_ROOT / "docs" / "integration-contract.md"
ENGINE_RESOLUTION = REPO_ROOT / "docs" / "engine-resolution.md"
ENGINE_CONTRACT_TESTS = REPO_ROOT / "docs" / "engine-contract-tests.md"
COMPONENT_DISCOVERY = REPO_ROOT / "docs" / "component-discovery.md"
CLI_CONVENTIONS = REPO_ROOT / "docs" / "cli-conventions.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"
SRC_ROOT = REPO_ROOT / "src" / "create_forge"
ENGINE_ADAPTER = SRC_ROOT / "engine.py"

TESTED_ENGINE_REQUIREMENT = "forge-template==0.2.0"
TESTED_ENGINE_REVISION = "2158c85a46efffc7d8ea2d43e347b943359baed1"

# Every module reachable from create-forge's shipped entry point
# (`create_forge.cli:app`). `engine.py` is deliberately excluded -- it is the
# one module ADR 0013 permits to import forge_template, mirroring invariant
# 4's rule that runner.py is the only module touching Copier's Python API.
_SHIPPED_MODULES = ("cli", "prompts", "runner", "registry", "models", "config", "spec")

# The one dependency ADR 0012 governs: Copier today, the forge-template
# engine after cutover. Kept as a constant so both decisions' tests agree on
# what "the compatibility-line dependency" currently names.
COMPATIBILITY_LINE_DEPENDENCY = "copier"

# PEP 503 normalisation: case-fold and collapse runs of -._ to a single "-".
_NORMALISE_RE = re.compile(r"[-_.]+")


def _normalise(name: str) -> str:
    return _NORMALISE_RE.sub("-", name).lower()


def _declared_dependencies() -> dict[str, str]:
    """Every top-level dependency pyproject.toml declares, as {normalised
    name: full requirement string}.

    Reads `[project.dependencies]` only -- dependency-groups are dev-only
    tooling (ruff, pytest, ...) and never a runtime engine dependency.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    deps: list[str] = data["project"]["dependencies"]
    declared = {}
    for spec in deps:
        # A requirement string's name is everything before the first
        # version/marker/extra delimiter.
        match = re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*", spec)
        if match:
            declared[_normalise(match.group(0))] = spec
    return declared


def _declared_dependency_names() -> set[str]:
    """Every top-level dependency name pyproject.toml declares, normalised."""
    return set(_declared_dependencies())


def _dependabot_uv_ignores() -> list[dict[str, Any]]:
    """The `uv` ecosystem entry's `ignore` rules from .github/dependabot.yml.

    Returns an empty list if the entry has no `ignore` key at all, so a
    missing gate reads the same as an empty one to callers.
    """
    data = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    for entry in data["updates"]:
        if entry.get("package-ecosystem") == "uv":
            ignores: list[dict[str, Any]] = entry.get("ignore", [])
            return ignores
    return []


def test_no_engine_dependency_means_no_assigned_engine_range() -> None:
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
    expected = "| First engine line | Unassigned | 1 (defined; not yet supported) |"
    assert expected in contract_text, (
        "No forge-template dependency is declared yet, so the future engine "
        "range must stay unassigned while the defined protocol remains "
        "explicitly unsupported."
    )


def test_development_engine_pair_is_exact_and_immutable() -> None:
    """The Stage 06 pair is reproducible without becoming a runtime range."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    assert data["dependency-groups"]["engine"] == [TESTED_ENGINE_REQUIREMENT]
    source = data["tool"]["uv"]["sources"]["forge-template"]
    assert source["rev"] == TESTED_ENGINE_REVISION
    assert re.fullmatch(r"[0-9a-f]{40}", source["rev"])
    assert "forge-template" not in _declared_dependency_names()


def test_engine_contract_doc_is_linked_from_canonical_entry_points() -> None:
    link_re = re.compile(r"\([^)]*engine-contract-tests\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD, INTEGRATION_CONTRACT):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), (
            f"{path.name} does not link engine-contract-tests.md"
        )

    assert ENGINE_CONTRACT_TESTS.is_file()


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


def test_component_discovery_doc_is_linked_from_canonical_entry_points() -> None:
    """CF-06.02's living adapter contract must remain discoverable wherever
    contributors enter the engine integration documentation.
    """
    link_re = re.compile(r"\([^)]*component-discovery\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD, INTEGRATION_CONTRACT):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), f"{path.name} does not link component-discovery.md"

    assert COMPONENT_DISCOVERY.is_file()


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


def test_compatibility_line_dependency_keeps_a_strict_upper_bound() -> None:
    """ADR 0012: the compatibility-line dependency's declared range must
    have both a tested lower bound and a strict upper bound. This is live
    today against `copier`, not a placeholder for a future engine -- a PR
    that widens `copier`'s bound (e.g. to an unbounded `>=9.4`) must fail
    here before it can reach Dependabot's ignore rule at all.
    """
    declared = _declared_dependencies()
    spec = declared.get(COMPATIBILITY_LINE_DEPENDENCY)
    assert spec is not None, (
        f"{COMPATIBILITY_LINE_DEPENDENCY!r} is no longer a declared "
        "dependency -- update COMPATIBILITY_LINE_DEPENDENCY and this test "
        "to name whatever occupies the compatibility-line role now."
    )
    assert re.search(r">=\d", spec), f"{spec!r} has no tested lower bound"
    assert re.search(r"<\d", spec), f"{spec!r} has no strict upper bound"


def test_automation_cannot_cross_the_copier_compatibility_line() -> None:
    """ADR 0012: Dependabot's `uv` entry must ignore major-version updates
    for the compatibility-line dependency, so a new Copier major arrives
    only as a deliberate human PR, never an automated one.
    """
    ignores = _dependabot_uv_ignores()
    matching = [
        rule
        for rule in ignores
        if _normalise(str(rule.get("dependency-name", "")))
        == COMPATIBILITY_LINE_DEPENDENCY
    ]
    assert matching, (
        f".github/dependabot.yml's uv entry has no ignore rule for "
        f"{COMPATIBILITY_LINE_DEPENDENCY!r} -- see ADR 0012 and "
        "docs/engine-updates.md."
    )
    assert any(
        "version-update:semver-major" in rule.get("update-types", [])
        for rule in matching
    ), (
        f"the {COMPATIBILITY_LINE_DEPENDENCY!r} ignore rule does not block "
        "semver-major updates"
    )


def test_declaring_the_engine_requires_a_matching_automation_gate() -> None:
    """The self-arming half of ADR 0012: the moment a `forge-template`
    dependency is declared, .github/dependabot.yml must gain a matching
    ignore rule (major always; minor too while forge-template is pre-1.0) --
    otherwise the review gate this decision describes silently does not
    exist for the real engine. Vacuously true today, by design, since no
    such dependency is declared yet.
    """
    declared = _declared_dependencies()
    engine_spec = declared.get("forge-template")
    if engine_spec is None:
        return

    ignores = _dependabot_uv_ignores()
    matching = [
        rule
        for rule in ignores
        if _normalise(str(rule.get("dependency-name", ""))) == "forge-template"
    ]
    assert matching, (
        "pyproject.toml now declares a forge-template dependency, but "
        ".github/dependabot.yml's uv entry has no matching ignore rule -- "
        "follow ADR 0012 and add one before this can merge."
    )
    update_types = {
        update_type for rule in matching for update_type in rule.get("update-types", [])
    }
    assert "version-update:semver-major" in update_types
    is_pre_1_0 = re.search(r">=0\.", engine_spec) is not None
    if is_pre_1_0:
        assert "version-update:semver-minor" in update_types, (
            "forge-template is pre-1.0, so a minor bump is a compatibility "
            "line too -- the ignore rule must block semver-minor as well "
            "as semver-major (ADR 0012)."
        )


def _imported_top_level_names(path: Path) -> set[str]:
    """Every top-level module name a file imports, via `import` or `from`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_engine_adapter_imports_only_the_public_forge_template_facade() -> None:
    """No create-forge adapter call may reach into a private engine module."""
    tree = ast.parse(
        ENGINE_ADAPTER.read_text(encoding="utf-8"), filename=str(ENGINE_ADAPTER)
    )
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("forge_template")
    }

    assert imported_modules == {"forge_template"}


def test_shipped_cli_modules_do_not_import_the_engine() -> None:
    """ADR 0013: `engine.py` is the only module allowed to import
    `forge_template`, mirroring invariant 4's rule that `runner.py` is the
    only module touching Copier's Python API. `forge_template` lives in a
    dev-only dependency group (pinned to an unreleased commit) -- if any
    module reachable from `create-forge`'s shipped entry point ever imports
    it, a built wheel stops installing for real users.
    """
    for module_name in _SHIPPED_MODULES:
        path = SRC_ROOT / f"{module_name}.py"
        imported = _imported_top_level_names(path)
        assert "forge_template" not in imported, (
            f"{path.name} imports forge_template directly -- only engine.py "
            "may (ADR 0013). Route the call through create_forge.engine "
            "instead."
        )
