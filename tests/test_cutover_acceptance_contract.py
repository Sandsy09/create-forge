"""Guards for the engine-default cutover acceptance contract (CF-16.03, ADR 0042).

`docs/engine-cutover-acceptance.md` is a *decision*, not a shipped interface: it
fixes the cutover release (`create-forge 0.4.0`), the supported OS / Python /
install-mode matrix, the cross-repository acceptance matrix and release gates,
and the rollback / support / deprecation windows — none of which any release
has performed.

Same discipline as `tests/test_engine_default_contract.py`,
`tests/test_engine_lifecycle_contract.py` and `forge-template`'s
`tests/test_cutover_gates.py`:

- **Derived assertions** read the live pre-cutover repository (`pyproject.toml`,
  the CLI) and the roadmap filing manifests, so a claim about *today's* state
  that silently changes fails here.
- **Structural checks** keep the acceptance matrix honest: every row names an
  issue that is actually filed, and every Stage 18 client child owns a row.
- **Tripwires** assert the pre-cutover state deliberately, each naming the
  CF-EPIC-18 issue whose merge must flip it. When the cutover lands they fail
  on purpose, forcing whoever implements it to move the affected rule out of
  `docs/engine-cutover-acceptance.md`'s "decided" voice and into
  `docs/cli-conventions.md` / `docs/integration-contract.md`'s "in force" voice
  in the same change.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

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


def test_create_forge_is_still_on_the_pre_cutover_line() -> None:
    """ADR 0042 decision 1 fixes the cutover as `create-forge 0.4.0`. Today the
    package is still on the 0.3 line -- this reads the live version, so the
    release bump cannot land without updating the contract.
    """
    version = str(_project()["version"])
    assert version.startswith("0.3."), version


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
# Tripwires -- fail deliberately when the cutover lands                        #
# --------------------------------------------------------------------------- #


def test_tripwire_version_is_not_yet_the_cutover_release() -> None:
    """Flips when CF-18.07 (#164) bumps `pyproject.toml` to the 0.4 line for
    the cutover release. Update docs/engine-cutover-acceptance.md's Status and
    this tripwire in that change.
    """
    assert not str(_project()["version"]).startswith("0.4."), _project()["version"]


def test_tripwire_user_guide_still_says_the_cutover_is_unscheduled() -> None:
    """Flips when CF-18.06 (#163) updates the user guide for the shipped
    cutover. Today docs/user-guide/reference.md's "What's next" still says the
    engine default is a planned direction with no scheduled release.
    """
    text = " ".join(USER_GUIDE_REFERENCE.read_text(encoding="utf-8").split())
    assert "no scheduled release" in text


def test_tripwire_no_installed_cutover_suite_exists_yet() -> None:
    """Flips when CF-18.06 (#163) adds the installed-console cutover suite the
    acceptance matrix names (`tests/test_e2e_installed_cutover.py`, the analogue
    of tests/test_e2e_installed_rollout.py).
    """
    assert not (REPO_ROOT / "tests" / "test_e2e_installed_cutover.py").exists()
