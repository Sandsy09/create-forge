"""CF-22.03 (ADR 0054): the installed update-safety evidence cannot go stale
silently, and cannot quietly stop covering a platform.

`release.yml` runs no tests -- a release is cut from a green `main`. So the
enforcement point for "if safety-relevant candidate code changes, refresh the
affected evidence before publication" (CF-22.03 AC-03; CF-21.03's own criteria)
is a fast-suite test that turns `main` red when the code the installed suite
proves has changed since the record was written.

That is a nudge with teeth, not a proof: updating the recorded digest without
re-running the installed suite satisfies it. The record says so, and the pull
request that changes it is where that is reviewed.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import re
from pathlib import Path

from candidate_evidence import safety_digest

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD = REPO_ROOT / "docs" / "update-safety-validation.md"
TESTS = REPO_ROOT / "tests"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
INSTALLED_SUITE = "tests/test_e2e_installed_update_safety.py"

_DIGEST_ROW = re.compile(
    r"Safety-relevant source digest\s*\|\s*`(sha256:[0-9a-f]{64})`"
)
_CITED_TEST = re.compile(r"`(test_[A-Za-z0-9_]+)`")
_DEFINED_TEST = re.compile(r"^\s*(?:async\s+)?def (test_[A-Za-z0-9_]+)\(", re.M)


def _record() -> str:
    return RECORD.read_text(encoding="utf-8")


def test_the_recorded_safety_digest_matches_the_source() -> None:
    match = _DIGEST_ROW.search(_record())
    assert match, (
        "docs/update-safety-validation.md has no 'Safety-relevant source digest' "
        "row; paste the table `uv run poe evidence:candidate` prints"
    )
    recorded, actual = match.group(1), safety_digest(REPO_ROOT)

    assert recorded == actual, (
        "safety-relevant code changed since the installed update-safety evidence "
        "was recorded (CF-22.03, ADR 0054).\n"
        f"  recorded: {recorded}\n  current:  {actual}\n"
        "Re-run the installed suite (`uv run pytest "
        "tests/test_e2e_installed_update_safety.py`), then refresh the "
        "'Recorded validation' table in docs/update-safety-validation.md with "
        "`uv run poe evidence:candidate`. The files hashed are listed in "
        "scripts/candidate_evidence.py."
    )


def test_every_test_the_record_cites_exists() -> None:
    """The record's acceptance-criteria map names tests; a renamed or deleted
    test must fail here, not leave a map pointing at nothing.
    """
    defined: set[str] = set()
    for path in TESTS.glob("test_*.py"):
        defined.update(_DEFINED_TEST.findall(path.read_text(encoding="utf-8")))

    cited = set(_CITED_TEST.findall(_record()))

    assert cited, "the record cites no tests"
    assert not cited - defined, (
        f"record cites tests that do not exist: {cited - defined}"
    )


def test_the_record_states_the_cf_21_03_release_prerequisite() -> None:
    text = _record()

    assert "## Release prerequisite" in text
    assert "CF-21.03" in text
    assert "0054-verify-installed-update-safety-on-the-release-candidate.md" in text


def test_the_installed_suite_runs_on_windows_ci() -> None:
    """The Windows e2e job runs a hand-picked list of tests, so a new installed
    module is silently absent from it unless it is named there.
    """
    ci = CI.read_text(encoding="utf-8")
    windows = ci[ci.index("e2e-windows:") : ci.index("all-green:")]

    assert INSTALLED_SUITE in windows
