"""Regression checks for the prepared roadmap filing packs."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check_roadmaps.py"


def run_check(
    root: Path, mirror: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the validator without importing application or provider modules."""
    command = [sys.executable, str(CHECKER), "--root", str(root)]
    if mirror:
        command.extend(["--mirror", str(mirror)])
    # The command is the current interpreter and our repository-owned checker.
    return subprocess.run(  # noqa: S603
        command, capture_output=True, text=True, check=False
    )


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    """Copy only prepared metadata into a disposable validation fixture."""
    for version in (3, 4):
        shutil.copytree(
            ROOT / f"docs/roadmap-v{version}", tmp_path / f"docs/roadmap-v{version}"
        )
    (tmp_path / ".github").mkdir()
    shutil.copyfile(ROOT / ".github/labels.toml", tmp_path / ".github/labels.toml")
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(CHECKER, tmp_path / "scripts/check_roadmaps.py")
    return tmp_path


def test_prepared_roadmaps_are_complete() -> None:
    """The committed packs have complete bodies, metadata, links and a valid DAG."""
    result = run_check(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "8 epics, 30 children, 45 review obligations" in result.stdout


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("label", "unknown label"),
        ("body", "missing Outcome"),
        ("trace", "Missing or duplicate review criteria"),
        ("cycle", "Dependency cycle"),
        ("streamlit", "Streamlit must enter"),
        ("status", "inconsistent blocked status"),
    ],
)
def test_invalid_packs_fail_closed(pack: Path, mutation: str, message: str) -> None:
    """Reject incomplete drafts and dangerous filing metadata before GitHub writes."""
    version = 4 if mutation == "streamlit" else 3
    manifest_path = pack / f"docs/roadmap-v{version}/github-issues/filing-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identifier = "FT-19.01" if mutation == "streamlit" else "FT-15.02"
    item = next(row for row in manifest["issues"] if row["id"] == identifier)
    body_path = pack / f"docs/roadmap-v{version}" / item["body"]
    body = body_path.read_text(encoding="utf-8")
    if mutation == "label":
        item["labels"].append("area:invented")
    elif mutation == "body":
        body = body.replace("## Outcome", "## Missing outcome")
    elif mutation == "trace":
        manifest["traceability"].pop()
    elif mutation == "status":
        item["labels"].remove("status:blocked")
    else:
        old = item["blocked_by"][0]
        replacement = "CF-18.07" if mutation == "streamlit" else "FT-15.04"
        item["blocked_by"] = [replacement]
        # Keep the link target valid so the graph check, not link validation,
        # rejects the mutated endpoint.
        body = re.sub(
            rf"Blocked\s+by\s+\[{re.escape(old)}\]",
            f"Blocked by [{replacement}]",
            body,
        )
    body_path.write_text(body, encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    result = run_check(pack)
    assert result.returncode == 1
    assert message in result.stderr


def test_mirror_drift_is_rejected(pack: Path) -> None:
    """A changed mirror cannot pass the shared-artifact validation."""
    page = pack / "docs/roadmap-v3/README.md"
    page.write_text(page.read_text(encoding="utf-8") + "\nDrift.\n", encoding="utf-8")
    result = run_check(ROOT, pack)
    assert result.returncode == 1
    assert "Mirror differs" in result.stderr
