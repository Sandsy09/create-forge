"""CF-29.02 (ADR 0062): the installed batch evidence stays wired into CI.

The Windows e2e job runs a hand-picked list of tests, so a module (or a
selection) is silently absent from it unless it is named there. These fast,
offline checks fail in the ordinary suite when that wiring is dropped, rather
than the evidence quietly ceasing to run on the second OS.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
INSTALLED_BATCH_SUITE = "tests/test_e2e_installed_batch.py"

# The tests the Windows selection must keep running, by their ids' stems.
_SELECTED_IDS = ("alone",)
# And the ones it deliberately leaves to Linux.
_EXCLUDED_WORDS = ("window_edge", "recipe", "jupyter", "scientific")


def _windows_job() -> str:
    ci = CI.read_text(encoding="utf-8")
    return ci[ci.index("e2e-windows:") : ci.index("all-green:")]


def test_the_installed_batch_suite_runs_on_windows_ci() -> None:
    assert INSTALLED_BATCH_SUITE in _windows_job()


def test_the_windows_batch_selection_keeps_the_alone_composition() -> None:
    """The step exists to run the `alone` composition end to end on Windows. Its
    `-k` expression excludes by name, so a careless extra exclusion (or a
    renamed id) could silently drop it; pin both halves of the contract.
    """
    line = next(
        line
        for line in _windows_job().splitlines()
        if INSTALLED_BATCH_SUITE in line and "-k" in line
    )
    expression = line.split("-k", 1)[1].strip().strip('"')

    for word in _EXCLUDED_WORDS:
        assert f"not {word}" in expression, f"{word!r} is no longer excluded"
    for stem in _SELECTED_IDS:
        assert stem not in expression, f"{stem!r} must not be excluded from Windows"


def test_the_batch_module_still_has_the_alone_composition_id() -> None:
    """The selection above relies on the id `alone`; fail here if it is renamed."""
    source = (REPO_ROOT / INSTALLED_BATCH_SUITE).read_text(encoding="utf-8")
    assert 'slug="alone"' in source
