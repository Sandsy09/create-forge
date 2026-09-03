"""The downstream client reference (CF-09.02, ADR 0023).

Exercises the real `forge_template` package -- the `engine` optional extra
(ADR 0018), present when `uv sync --all-extras` was used to set up this
checkout -- mirroring `tests/test_engine_adapter.py`'s style. No network, no
subprocess: `examples/downstream_cli.py` is imported in-process as
`downstream_cli` (see `pyproject.toml`'s `pytest.pythonpath`).

See docs/downstream-client-reference.md for the contract these tests
characterize.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from forge_template import EngineInfo, discover_components

import downstream_cli as ref

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_ROOT = REPO_ROOT / "examples"
REFERENCE_CLIENT = EXAMPLES_ROOT / "downstream_cli.py"
POLICIES_DIR = EXAMPLES_ROOT / "policies"


def _engine_info(
    *,
    package_version: str = "0.4.0",
    projectspec_protocols: tuple[int, ...] = (1,),
    component_manifest_protocols: tuple[int, ...] = (1,),
) -> EngineInfo:
    return EngineInfo(
        package_version=package_version,
        projectspec_protocols=projectspec_protocols,
        component_manifest_protocols=component_manifest_protocols,
    )


# -- Negotiation ---------------------------------------------------------------


def test_negotiate_accepts_the_real_installed_engine() -> None:
    """No exception -- the installed engine is within this client's own
    declared range, independent of `create_forge.compat`.
    """
    ref.negotiate(_engine_info())


def test_negotiate_rejects_an_out_of_range_package_version() -> None:
    with pytest.raises(ref.UnsupportedEngineError) as excinfo:
        ref.negotiate(_engine_info(package_version="0.2.0"))

    message = str(excinfo.value)
    assert "0.2.0" in message
    assert ref.SUPPORTED_ENGINE_RANGE in message
    assert "pip install" in message


def test_negotiate_rejects_a_non_overlapping_projectspec_protocol() -> None:
    with pytest.raises(ref.UnsupportedEngineError) as excinfo:
        ref.negotiate(_engine_info(projectspec_protocols=(2,)))

    message = str(excinfo.value)
    assert "[2]" in message
    assert "[1]" in message
    assert "upgrade or downgrade" in message


# -- Nothing written on a failed negotiation ------------------------------------


def test_main_exits_3_and_writes_nothing_on_an_unsupported_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        ref, "get_engine_info", lambda: _engine_info(package_version="0.2.0")
    )
    destination = tmp_path / "out"

    exit_code = ref.main(["--name", "Example Service", "--output", str(destination)])

    assert exit_code == ref.EXIT_UNSUPPORTED_ENGINE
    assert not destination.exists()


# -- Authority order -------------------------------------------------------------


def test_policy_default_fills_an_absent_archetype_and_is_recorded(
    tmp_path: Path,
) -> None:
    policy = tmp_path / "org.json"
    policy.write_text(
        json.dumps(
            {
                "policy_version": 1,
                "id": "example-org",
                "defaults": {"archetype": "library"},
            }
        ),
        encoding="utf-8",
    )
    merged = ref.merge_policies([ref.load_policy(policy)])

    selection = ref.resolve(
        merged,
        explicit=ref.ExplicitSelection(),
        profile_default_archetype=None,
        catalogue=discover_components(),
    )

    assert selection.archetype == "library"
    assert selection.applied_policy_ids == ("example-org",)


def test_an_explicit_archetype_overrides_the_policy_default(tmp_path: Path) -> None:
    policy = tmp_path / "org.json"
    policy.write_text(
        json.dumps(
            {
                "policy_version": 1,
                "id": "example-org",
                "defaults": {"archetype": "library"},
            }
        ),
        encoding="utf-8",
    )
    merged = ref.merge_policies([ref.load_policy(policy)])

    selection = ref.resolve(
        merged,
        explicit=ref.ExplicitSelection(archetype="cli"),
        profile_default_archetype=None,
        catalogue=discover_components(),
    )

    assert selection.archetype == "cli"


def test_explicitly_empty_capabilities_is_distinct_from_omitted() -> None:
    """Protocol v1: "an explicitly empty list is still an explicit choice."

    `ExplicitSelection(capabilities=None)` is absent -- a policy default may
    still fill it; `ExplicitSelection(capabilities=())` is an explicit choice
    of "none" and is never overwritten by a policy default, even a non-empty
    one. Exercised through `apply_authority_order` directly -- the real
    production catalogue has zero capabilities, so `resolve()`'s own
    catalogue-validation step would reject any non-empty capability id
    before this distinction was even reached.
    """
    merged = ref.MergedPolicy(default_capabilities=frozenset({"documentation"}))

    _, absent_capabilities, _ = ref.apply_authority_order(
        merged,
        explicit=ref.ExplicitSelection(archetype="library", capabilities=None),
        profile_default_archetype=None,
    )
    _, explicit_empty_capabilities, _ = ref.apply_authority_order(
        merged,
        explicit=ref.ExplicitSelection(archetype="library", capabilities=()),
        profile_default_archetype=None,
    )

    assert absent_capabilities == frozenset({"documentation"})
    assert explicit_empty_capabilities == frozenset()


def test_cli_no_capabilities_flag_is_distinct_from_omitting_capability() -> None:
    """The same rule, exercised through `main`'s own argument parsing rather
    than `ExplicitSelection` directly.
    """
    with_flag = ref._build_parser().parse_args(["--name", "x", "--no-capabilities"])
    without_flag = ref._build_parser().parse_args(["--name", "x"])

    assert with_flag.no_capabilities is True
    assert without_flag.no_capabilities is False
    assert with_flag.capabilities is None
    assert without_flag.capabilities is None


# -- Violations --------------------------------------------------------------


def test_an_explicitly_forbidden_archetype_is_a_violation() -> None:
    merged = ref.MergedPolicy(forbidden_archetypes=frozenset({"cli"}))

    with pytest.raises(ref.PolicyError) as excinfo:
        ref.resolve(
            merged,
            explicit=ref.ExplicitSelection(archetype="cli"),
            profile_default_archetype=None,
            catalogue=discover_components(),
        )

    assert excinfo.value.category == "organisation-policy-violation"
    assert excinfo.value.details[0].code == "forbidden-selection-selected"


def test_main_exits_1_and_writes_nothing_on_a_policy_violation(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "out"

    exit_code = ref.main(
        [
            "--name",
            "Example Service",
            "--archetype",
            "cli",
            "--policy",
            str(POLICIES_DIR / "example-baseline.json"),
            "--output",
            str(destination),
        ]
    )

    assert exit_code == ref.EXIT_FAILURE
    assert not destination.exists()


@pytest.mark.parametrize(
    "order",
    [
        ("example-baseline.json", "example-restricted.json"),
        ("example-restricted.json", "example-baseline.json"),
    ],
)
def test_the_shipped_policy_pair_conflicts_identically_under_either_order(
    order: tuple[str, str],
) -> None:
    """The documented irreconcilable pair fails the same way regardless of
    which document is loaded first -- protocol v1: "these contradictions
    fail independently of input order."
    """
    policies = [ref.load_policy(POLICIES_DIR / name) for name in order]

    with pytest.raises(ref.PolicyError) as excinfo:
        ref.merge_policies(policies)

    assert excinfo.value.category == "organisation-policy-conflict"
    assert excinfo.value.details[0].code == "default-requirement-conflict"


def test_a_malformed_policy_document_is_invalid(tmp_path: Path) -> None:
    policy = tmp_path / "bad.json"
    policy.write_text(
        json.dumps({"policy_version": 2, "id": "example-bad"}), encoding="utf-8"
    )

    with pytest.raises(ref.PolicyError) as excinfo:
        ref.load_policy(policy)

    assert excinfo.value.category == "invalid-organisation-policy"
    assert excinfo.value.details[0].code == "unsupported-policy-version"


def test_an_empty_policy_document_is_invalid(tmp_path: Path) -> None:
    policy = tmp_path / "empty.json"
    policy.write_text(
        json.dumps({"policy_version": 1, "id": "example-empty"}), encoding="utf-8"
    )

    with pytest.raises(ref.PolicyError) as excinfo:
        ref.load_policy(policy)

    assert excinfo.value.category == "invalid-organisation-policy"
    assert excinfo.value.details[0].code == "empty-policy"


# -- A real write ----------------------------------------------------------------


def test_main_writes_a_real_project_with_no_forge_package_reference(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "example-service"

    exit_code = ref.main(
        [
            "--name",
            "Example Service",
            "--policy",
            str(POLICIES_DIR / "example-baseline.json"),
            "--output",
            str(destination),
        ]
    )

    assert exit_code == ref.EXIT_OK
    pyproject = destination / "pyproject.toml"
    assert pyproject.is_file()

    for path in destination.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert "forge-template" not in text
            assert "create-forge" not in text


def test_main_refuses_a_non_empty_destination_and_writes_nothing_more(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "keep.txt").write_text("already here", encoding="utf-8")

    exit_code = ref.main(
        [
            "--name",
            "Example Service",
            "--policy",
            str(POLICIES_DIR / "example-baseline.json"),
            "--output",
            str(destination),
        ]
    )

    assert exit_code == ref.EXIT_FAILURE
    assert [p.name for p in destination.iterdir()] == ["keep.txt"]


# -- Boundary guard (AST) ---------------------------------------------------------


def test_imports_no_create_forge_module() -> None:
    """CF-09.02's own fifth acceptance criterion: this reference must not
    depend on `create-forge` internals -- mirrored from
    `tests/test_engine_contract.py::test_shipped_cli_modules_do_not_import_the_engine`.
    """
    tree = ast.parse(
        REFERENCE_CLIENT.read_text(encoding="utf-8"), filename=str(REFERENCE_CLIENT)
    )
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])

    assert "create_forge" not in names


def test_imports_only_the_top_level_forge_template_facade() -> None:
    """Mirrors
    `test_engine_contract.py::test_engine_adapter_imports_only_the_public_forge_template_facade`
    -- a private `forge_template.*` submodule import would defeat the point
    of a public-facade reference.
    """
    tree = ast.parse(
        REFERENCE_CLIENT.read_text(encoding="utf-8"), filename=str(REFERENCE_CLIENT)
    )
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith("forge_template")
    }

    assert imported_modules == {"forge_template"}


# -- Fixture neutrality -----------------------------------------------------------


def test_shipped_policies_are_example_prefixed_and_reference_real_components() -> None:
    """Criterion 4 ("avoid organisation-sensitive configuration") as a test
    rather than a promise, mirroring forge-template's own
    `test_fixture_policies_carry_no_organisation_specific_values`.
    """
    catalogue_ids = {d.id for d in discover_components()}
    policy_files = sorted(POLICIES_DIR.glob("*.json"))
    assert policy_files, "no policy fixtures found under examples/policies/"

    for path in policy_files:
        policy = ref.load_policy(path)
        assert policy.id.startswith("example-"), (
            f"{path.name}: id {policy.id!r} is not example-prefixed"
        )

        referenced = {
            policy.default_archetype,
            policy.required_archetype,
            *policy.forbidden_archetypes,
            *policy.default_capabilities,
            *policy.required_capabilities,
            *policy.forbidden_capabilities,
            *policy.default_platforms,
            *policy.required_platforms,
            *policy.forbidden_platforms,
        } - {None}
        unknown = referenced - catalogue_ids
        assert not unknown, f"{path.name} references unknown component(s): {unknown}"
