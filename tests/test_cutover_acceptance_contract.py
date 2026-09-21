"""Guards for the engine-default cutover acceptance contract (CF-16.03, ADR 0042).

`docs/engine-cutover-acceptance.md` fixed the cutover release
(`create-forge 0.4.0`), the supported OS / Python / install-mode matrix, the
cross-repository acceptance matrix and release gates, and the rollback /
support / deprecation windows. CF-18.01 through CF-18.06 implemented and
validated all of it on `main`; CF-18.07 (#164, ADR 0049) published it.

Same discipline as `tests/test_engine_default_contract.py`,
`tests/test_engine_lifecycle_contract.py` and `forge-template`'s
`tests/test_cutover_gates.py`:

- **Derived assertions** read the live repository (`pyproject.toml`, the CLI)
  and the roadmap filing manifests, so a claim about *today's* state that
  silently changes fails here.
- **Structural checks** keep the acceptance matrix honest: every row names an
  issue that is actually filed, and every Stage 18 client child owns a row.

No tripwires remain. `docs/engine-cutover-acceptance.md`'s last pre-publication
claims and `test_tripwire_version_is_not_yet_the_cutover_release` -- the final
one -- were replaced by CF-18.07 with the derived assertions below, the same
"flip the tripwire into a derived check" move CF-18.06 made for its own two.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from packaging.version import Version

from create_forge import compat

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
ADR_0042 = (
    REPO_ROOT / "docs" / "adr" / "0042-engine-cutover-acceptance-and-support-policy.md"
)
ENGINE_CUTOVER_ACCEPTANCE = REPO_ROOT / "docs" / "engine-cutover-acceptance.md"
USER_GUIDE_REFERENCE = REPO_ROOT / "docs" / "user-guide" / "reference.md"
FILING_MANIFESTS = (
    REPO_ROOT / "docs" / "roadmap-v3" / "github-issues" / "filing-manifest.json",
    REPO_ROOT / "docs" / "roadmap-v4" / "github-issues" / "filing-manifest.json",
)

# ADR 0042 decision 10: every acceptance-matrix row is owned by an
# already-filed Stage 18 child; the matrix files no new issue.
_STAGE_18_ROW_OWNERS = (
    "CF-18.01",
    "CF-18.02",
    "CF-18.03",
    "CF-18.04",
    "CF-18.05",
    "CF-18.06",
    "CF-18.07",
    "FT-18.01",
)

_ISSUE_TOKEN = re.compile(r"(?:CF|FT)-(?:EPIC-)?\d{2}(?:\.\d{2})?")


def _pyproject() -> dict[str, Any]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _project() -> dict[str, Any]:
    project: dict[str, Any] = _pyproject()["project"]
    return project


def _contract() -> str:
    return ENGINE_CUTOVER_ACCEPTANCE.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The body between ``## heading`` and the next ``## `` heading."""
    marker = f"\n## {heading}\n"
    start = text.index(marker) + len(marker)
    rest = text[start:]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _table_rows(block: str) -> list[list[str]]:
    """Every 4-cell pipe row in ``block``, header and separator rows dropped."""
    rows: list[list[str]] = []
    for raw in block.splitlines():
        stripped = raw.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != 4:
            continue
        if cells[0] in {"Check", ""} or set(cells[0]) <= {"-", ":", " "}:
            continue
        rows.append(cells)
    return rows


def _filed_issue_ids() -> set[str]:
    ids: set[str] = set()
    for manifest in FILING_MANIFESTS:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        ids.update(issue["id"] for issue in data["issues"])
    return ids


def _matrix_rows() -> list[list[str]]:
    return _table_rows(_section(_contract(), "The cross-repository acceptance matrix"))


def _matrix_owner_tokens() -> set[str]:
    """Every issue token in the Owner and First-required-at columns."""
    tokens: set[str] = set()
    for _check, _command, owner, first in _matrix_rows():
        tokens.update(_ISSUE_TOKEN.findall(owner))
        tokens.update(_ISSUE_TOKEN.findall(first))
    return tokens


# --------------------------------------------------------------------------- #
# Derived assertions -- today's state, read from the live repository          #
# --------------------------------------------------------------------------- #


def test_create_forge_is_at_or_past_the_cutover_release() -> None:
    """ADR 0042 decision 1 fixed the cutover as `create-forge 0.4.0`; CF-18.07
    (ADR 0049) published it. This reads the live version, so a version *behind*
    the cutover cannot silently contradict this contract's own claim. ADR 0056
    (CF-21.03) moved the package on to `0.5.0`: the cutover release is a floor,
    not the current line, which `compat.INTEGRATION_LINE` tracks separately.
    """
    version = Version(str(_project()["version"]))
    assert version >= Version("0.4.0"), version


def test_supported_python_window_is_unchanged() -> None:
    """ADR 0042 decision 8: the floor does not move at the cutover, and the
    classifiers enumerate the active window (today 3.11-3.14).
    """
    project = _project()
    assert project["requires-python"] == ">=3.11"
    prefix = "Programming Language :: Python :: 3."
    minors = sorted(
        int(c.rsplit(".", 1)[1]) for c in project["classifiers"] if c.startswith(prefix)
    )
    assert minors == [11, 12, 13, 14], minors


def test_engine_is_required_and_copier_is_the_legacy_extra() -> None:
    """CF-18.01 adopted the `>=0.5,<0.6` cutover line: `forge-template` is a
    required dependency now, and `copier` moved into the optional `legacy`
    extra (ADR 0040 decisions 1/2).
    """
    project = _project()
    required = " ".join(project["dependencies"])
    assert "forge-template" in required
    assert "copier" not in required
    extras = project["optional-dependencies"]
    assert any(str(dep).startswith("copier") for dep in extras.get("legacy", []))


def test_adr_and_contract_exist_and_name_their_review_obligations_literally() -> None:
    assert ADR_0042.is_file()
    assert ENGINE_CUTOVER_ACCEPTANCE.is_file()
    adr = ADR_0042.read_text(encoding="utf-8")
    contract = _contract()
    for text, name in ((adr, "ADR 0042"), (contract, "the contract")):
        for obligation in ("CF-ROADMAP-01-AC-06", "CF-ROADMAP-01-EX-04"):
            assert obligation in text, f"{name} does not name {obligation}"
        assert "create-forge 0.4.0" in text, f"{name} does not name the cutover release"


def test_contract_points_at_the_authoritative_living_docs() -> None:
    contract = _contract()
    assert "cli-conventions.md" in contract
    assert "integration-contract.md" in contract


def test_contract_names_the_supported_matrix_axes() -> None:
    contract = _contract()
    for install_mode in (
        "uvx create-forge",
        "uv tool install create-forge",
        "pip install create-forge",
        "create-forge[legacy]",
    ):
        assert install_mode in contract, f"contract does not name `{install_mode}`"
    assert "latest four final CPython" in contract
    for platform in ("ubuntu-latest", "windows-latest", "macOS"):
        assert platform in contract, f"contract does not mention {platform}"


# --------------------------------------------------------------------------- #
# Structural checks -- the acceptance matrix stays honest                     #
# --------------------------------------------------------------------------- #


def test_matrix_has_rows() -> None:
    assert len(_matrix_rows()) >= 15


def test_every_matrix_row_names_a_filed_issue() -> None:
    """`forge-template`'s test_cutover_gates.py checks the same thing against
    its own manifest: a row may not cite an issue number that was never filed.
    """
    filed = _filed_issue_ids()
    for check, _command, owner, first in _matrix_rows():
        tokens = set(_ISSUE_TOKEN.findall(owner)) | set(_ISSUE_TOKEN.findall(first))
        assert tokens, f"matrix row names no owning issue: {check!r}"
        unfiled = tokens - filed
        assert not unfiled, f"matrix row {check!r} names unfiled issue(s): {unfiled}"


def test_every_stage_18_child_owns_at_least_one_matrix_row() -> None:
    owned = _matrix_owner_tokens()
    missing = set(_STAGE_18_ROW_OWNERS) - owned
    assert not missing, f"no acceptance-matrix row is owned by: {sorted(missing)}"


# --------------------------------------------------------------------------- #
# Derived assertions -- the published cutover release                         #
# --------------------------------------------------------------------------- #


def test_diagnostic_line_tracks_the_cutover_release() -> None:
    """CF-18.07 (#164, ADR 0049) replaced the last tripwire,
    `test_tripwire_version_is_not_yet_the_cutover_release`, with this derived
    pair: `compat.INTEGRATION_LINE` moved to the published release's line, and
    the acceptance contract's own Status section no longer claims the cutover
    hasn't shipped. ADR 0056 (CF-21.03) moved the line on to `v0.5.x-engine`
    for the Streamlit provider release; the contract's text stays a statement
    about the 0.4.0 cutover, which is why only the line literal moved.
    """
    assert compat.INTEGRATION_LINE == "v0.5.x-engine"
    text = " ".join(_contract().split())
    assert "has published yet" not in text
    assert "create-forge 0.4.0" in text


def test_user_guide_says_the_cutover_has_shipped() -> None:
    """CF-18.06 (#163, ADR 0048 decision 5) updated the user guide for the
    shipped cutover -- this replaces the tripwire that asserted the opposite
    (`docs/user-guide/reference.md`'s "What's next" used to say the engine
    default was a planned direction with no scheduled release).
    """
    text = " ".join(USER_GUIDE_REFERENCE.read_text(encoding="utf-8").split())
    assert "no scheduled release" not in text
    assert "Engine-Default Cutover has shipped" in text


def test_installed_cutover_suite_covers_the_cf_18_05_scenarios() -> None:
    """CF-18.05 (#162, ADR 0047 rule 5) created
    `tests/test_e2e_installed_cutover.py` -- the acceptance matrix's own row
    204 names this file as CF-18.05's evidence, ahead of the tripwire this
    test replaces, which had assumed CF-18.06 (#163) would create it first.
    """
    suite = REPO_ROOT / "tests" / "test_e2e_installed_cutover.py"
    assert suite.is_file()
    text = suite.read_text(encoding="utf-8")
    for needle in (
        "def test_legacy_extra_installs_copier",
        "def test_legacy_generation_and_update_against_a_local_tagged_template",
        "def test_legacy_route_without_the_extra_exits_3",
        "def test_preview_era_project_transition_is_rejected",
    ):
        assert needle in text, f"{suite.name} is missing {needle}"


def test_installed_cutover_suite_covers_the_cf_18_06_scenarios() -> None:
    """CF-18.06 (#163, ADR 0048) extended
    `tests/test_e2e_installed_cutover.py` past CF-18.05's own legacy-route and
    preview-transition scenarios to the rest of the installed cutover
    acceptance matrix -- this replaces the tripwire that asserted the
    opposite: install-mode coverage (row 172), the cutover-specific slice of
    the incompatible/invalid/failure matrix and the out-of-range/no-engine
    boundary (rows 219-220, the rest mapped onto
    `tests/test_e2e_installed_rollout.py` by `docs/engine-cutover-validation.md`
    per ADR 0048 decision 2), and the documented recipes (rows 228-229).
    """
    suite = REPO_ROOT / "tests" / "test_e2e_installed_cutover.py"
    text = suite.read_text(encoding="utf-8")
    for needle in (
        "def test_install_modes_uvx_ephemeral_resolves_and_generates",
        "def test_install_modes_uv_tool_install_resolves_and_generates",
        "def test_install_modes_pip_install_resolves_and_generates",
        "def test_install_modes_legacy_extra_resolves_and_generates",
        "def test_incompatible_engine_native_update_fails_closed_at_exit_3",
        "def test_boundary_incompatible_engine_via_engine_source_writes_nothing",
        "def test_recipe_diagnose_with_doctor",
    ):
        assert needle in text, f"{suite.name} is missing {needle}"
