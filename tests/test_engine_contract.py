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
FILESYSTEM_GENERATION = REPO_ROOT / "docs" / "filesystem-generation.md"
END_TO_END_TESTS = REPO_ROOT / "docs" / "end-to-end-tests.md"
DOWNSTREAM_CLIENT_REFERENCE = REPO_ROOT / "docs" / "downstream-client-reference.md"
CLI_CONVENTIONS = REPO_ROOT / "docs" / "cli-conventions.md"
COMPONENT_SELECTION = REPO_ROOT / "docs" / "component-selection.md"
DATA_SCIENCE_PREVIEW_VALIDATION = (
    REPO_ROOT / "docs" / "data-science-preview-validation.md"
)
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
CONTRIBUTING_MD = REPO_ROOT / "CONTRIBUTING.md"
SRC_ROOT = REPO_ROOT / "src" / "create_forge"
ENGINE_ADAPTER = SRC_ROOT / "engine.py"

ENGINE_REQUIREMENT = "forge-template>=0.4,<0.5"
UV_REQUIREMENT = "uv>=0.12,<0.13"

# Every module reachable from create-forge's shipped entry point
# (`create_forge.cli:app`). `engine.py` is deliberately excluded -- it is the
# one module ADR 0013 permits to import forge_template, mirroring invariant
# 4's rule that runner.py is the only module touching Copier's Python API.
_SHIPPED_MODULES = (
    "cli",
    "prompts",
    "runner",
    "registry",
    "models",
    "config",
    "spec",
    "staging",
    "compat",
)

# One of two compatibility-line dependencies ADR 0012 now governs -- Copier
# for the default `new` path. `forge-template` (ADR 0018) is the other, and
# is named directly in its own tests below rather than through this
# constant, since it has always had exactly one name.
COMPATIBILITY_LINE_DEPENDENCY = "copier"

# PEP 503 normalisation: case-fold and collapse runs of -._ to a single "-".
_NORMALISE_RE = re.compile(r"[-_.]+")


def _normalise(name: str) -> str:
    return _NORMALISE_RE.sub("-", name).lower()


def _required_dependencies() -> dict[str, str]:
    """Every unconditionally-required dependency, as {normalised name: spec}.

    Reads `[project.dependencies]` only -- dependency-groups are dev-only
    tooling (ruff, pytest, ...), never a runtime dependency, and optional
    extras are declared but not required.
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


def _declared_dependencies() -> dict[str, str]:
    """Every top-level dependency pyproject.toml declares -- required and
    optional-extra -- as {normalised name: full requirement string}.

    Dependency-groups (ruff, pytest, ...) are excluded: dev-only tooling,
    never a dependency a consumer's install resolves.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    deps: list[str] = list(data["project"]["dependencies"])
    for extra_deps in data["project"].get("optional-dependencies", {}).values():
        deps.extend(extra_deps)
    declared = {}
    for spec in deps:
        match = re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*", spec)
        if match:
            declared[_normalise(match.group(0))] = spec
    return declared


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


def test_engine_dependency_stays_out_of_required_dependencies() -> None:
    """ADR 0018: forge-template is declared as the optional `engine` extra,
    never a hard `[project.dependencies]` entry -- that is what keeps ADR
    0014's guarded `try/except ImportError` in cli.py meaningful, and what
    keeps a plain `pip install create-forge`/`uvx create-forge` from ever
    resolving it.
    """
    assert "forge-template" not in _required_dependencies(), (
        "forge-template must not be a required [project.dependencies] entry "
        "-- it belongs in [project.optional-dependencies].engine (ADR 0018), "
        "so the default `new` path never downloads an engine it doesn't call."
    )


def test_engine_dependency_is_an_optional_extra_with_an_assigned_range() -> None:
    """The engine range and its client-finalisation tool stay optional
    (#9/ADR 0018, ADR 0021, and ADR 0026's move to the 0.4 line).
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    assert data["project"]["optional-dependencies"]["engine"] == [
        ENGINE_REQUIREMENT,
        UV_REQUIREMENT,
    ]
    assert "uv" not in _required_dependencies()
    assert "sources" not in data.get("tool", {}).get("uv", {}), (
        "a committed [tool.uv.sources] override must not survive ADR 0018 -- "
        "the engine now resolves from PyPI like any other dependency."
    )
    assert "engine" not in data.get("dependency-groups", {}), (
        "the exact-pin development [dependency-groups].engine block is "
        "retired by ADR 0018."
    )

    contract_text = INTEGRATION_CONTRACT.read_text(encoding="utf-8")
    expected = f"| v0.3.x (`engine` extra) | `{ENGINE_REQUIREMENT}` | 1 (supported) |"
    assert expected in contract_text, (
        "docs/integration-contract.md's compatibility table must record the "
        "same range this test just verified in pyproject.toml (ADR 0026)."
    )


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


def test_filesystem_generation_doc_is_linked_from_canonical_entry_points() -> None:
    """CF-07.04's living staging/finalisation contract must remain
    discoverable wherever contributors enter the engine integration
    documentation, mirroring component-discovery.md's equivalent guard.
    """
    link_re = re.compile(r"\([^)]*filesystem-generation\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD, INTEGRATION_CONTRACT):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), (
            f"{path.name} does not link filesystem-generation.md"
        )

    assert FILESYSTEM_GENERATION.is_file()


def test_end_to_end_tests_doc_is_linked_from_canonical_entry_points() -> None:
    """CF-07.06's living end-to-end contract must remain discoverable
    wherever contributors enter the engine integration documentation,
    mirroring component-discovery.md's and filesystem-generation.md's
    equivalent guards.
    """
    link_re = re.compile(r"\([^)]*end-to-end-tests\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), f"{path.name} does not link end-to-end-tests.md"

    assert END_TO_END_TESTS.is_file()


def test_downstream_client_reference_is_linked_from_canonical_entry_points() -> None:
    """CF-09.02's living reference-client contract must remain discoverable
    wherever contributors enter the engine integration documentation,
    mirroring end-to-end-tests.md's equivalent guard.
    """
    link_re = re.compile(r"\([^)]*downstream-client-reference\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), (
            f"{path.name} does not link downstream-client-reference.md"
        )

    assert DOWNSTREAM_CLIENT_REFERENCE.is_file()


def test_component_selection_doc_is_linked_from_canonical_entry_points() -> None:
    """CF-13.02's living component-selection contract (ADR 0027) must remain
    discoverable wherever contributors enter the CLI and engine integration
    documentation, mirroring the equivalent guards above. It is a CLI-surface
    contract, so its third entry point is cli-conventions.md rather than
    integration-contract.md.
    """
    link_re = re.compile(r"\([^)]*component-selection\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD, CLI_CONVENTIONS):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), f"{path.name} does not link component-selection.md"

    assert COMPONENT_SELECTION.is_file()


def test_data_science_preview_validation_doc_is_linked_from_entry_points() -> None:
    """CF-13.05's living acceptance-evidence contract (ADR 0030) must remain
    discoverable wherever contributors enter the engine integration
    documentation, mirroring end-to-end-tests.md's equivalent guard.
    """
    link_re = re.compile(r"\([^)]*data-science-preview-validation\.md[^)]*\)")

    for path in (CLAUDE_MD, CONTRIBUTING_MD):
        text = path.read_text(encoding="utf-8")
        assert link_re.search(text), (
            f"{path.name} does not link data-science-preview-validation.md"
        )

    assert DATA_SCIENCE_PREVIEW_VALIDATION.is_file()


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


def test_forge_template_compatibility_line_keeps_a_strict_upper_bound() -> None:
    """ADR 0012/0018: forge-template is now the second compatibility-line
    dependency, mirroring the equivalent `copier` test above -- both a
    tested lower bound and a strict upper bound, checked directly rather
    than assumed from the extra's mere presence.
    """
    declared = _declared_dependencies()
    spec = declared.get("forge-template")
    assert spec is not None, (
        "forge-template must be declared in [project.optional-dependencies]."
        "engine (ADR 0018) for this test to check its bound."
    )
    assert re.search(r">=\d", spec), f"{spec!r} has no tested lower bound"
    assert re.search(r"<\d", spec), f"{spec!r} has no strict upper bound"


def test_automation_cannot_cross_the_forge_template_compatibility_line() -> None:
    """The self-arming half of ADR 0012: now that ADR 0018 declares a real
    `forge-template` dependency, .github/dependabot.yml must ignore both
    semver-major and semver-minor bumps for it -- pre-1.0, a minor version is
    itself a compatibility line, unlike `copier`'s major-only gate.
    """
    ignores = _dependabot_uv_ignores()
    matching = [
        rule
        for rule in ignores
        if _normalise(str(rule.get("dependency-name", ""))) == "forge-template"
    ]
    assert matching, (
        ".github/dependabot.yml's uv entry has no ignore rule for "
        "'forge-template' -- see ADR 0012, ADR 0018, and docs/engine-updates.md."
    )
    update_types = {
        update_type for rule in matching for update_type in rule.get("update-types", [])
    }
    assert "version-update:semver-major" in update_types, (
        "the 'forge-template' ignore rule does not block semver-major updates"
    )
    engine_spec = _declared_dependencies()["forge-template"]
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
