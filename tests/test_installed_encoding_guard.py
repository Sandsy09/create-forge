"""CF-23.02 (ADR 0057): the installed-console encoding evidence cannot quietly
stop covering the supported Python window, and this repository cannot quietly
start relying on the workaround this issue's outcome says is not required.

`docs/subprocess-output.md`/`docs/installed-encoding-validation.md` are the
narrative contract; this is the part of it a CI edit can silently break
without either failing loudly.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from tests.installed_client import DEFAULT_PYTHON

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
INSTALLED_SUITE = "tests/test_e2e_installed_encoding.py"

_JOB_HEADER = "e2e-windows-encoding:"
_NEXT_JOB_HEADER = "all-green:"


def _ci_text() -> str:
    return CI.read_text(encoding="utf-8")


def _job_text() -> str:
    text = _ci_text()
    start = text.index(_JOB_HEADER)
    end = text.index(_NEXT_JOB_HEADER, start)
    return text[start:end]


def _supported_python_window() -> list[str]:
    """The active CPython window, from `pyproject.toml`'s own classifiers --
    the same source `test_cutover_acceptance_contract.py`'s Python-window test
    reads, so the two can never silently disagree about what "the supported
    window" is.
    """
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    prefix = "Programming Language :: Python :: 3."
    minors = sorted(
        int(c.rsplit(".", 1)[1]) for c in project["classifiers"] if c.startswith(prefix)
    )
    return [f"3.{minor}" for minor in minors]


def test_the_job_exists_and_runs_the_installed_encoding_module() -> None:
    job = _job_text()

    assert INSTALLED_SUITE in job, (
        f"{_JOB_HEADER} does not run {INSTALLED_SUITE} -- CF-23.02's Windows "
        "matrix evidence would silently stop existing"
    )


def test_the_matrix_covers_both_edges_of_the_supported_python_window() -> None:
    """The matrix proves the edges of the supported window plus the
    repository's own default interpreter, the same "edges, not the whole
    window" reasoning `tests/test_e2e_installed_cutover.py`'s and
    `tests/test_e2e_installed_streamlit.py`'s own `_PYTHON_WINDOW_EDGES`
    already rely on for the identical `build_client(python=...)` mechanism --
    the interior of the window is proven by the `test` job's own full matrix
    and the `floor` job, not repeated here. A Python release entering or
    leaving the supported window must still move this matrix's edges in the
    same change.
    """
    job = _job_text()
    match = re.search(r"python:\s*\[([^\]]*)\]", job)
    assert match, f"{_JOB_HEADER} has no `python:` matrix list"
    matrix = sorted(re.findall(r'"(3\.\d+)"', match.group(1)))

    window = _supported_python_window()
    expected = sorted({window[0], window[-1], DEFAULT_PYTHON})
    assert matrix == expected, (
        f"matrix {matrix} does not match the expected edges-plus-default "
        f"{expected} of the supported window {window}"
    )


def test_no_workflow_job_forces_a_utf8_environment_variable() -> None:
    """CF-23.02's outcome is that no global forced-UTF-8 workaround is
    required for correctness -- made executable rather than left as a claim:
    neither variable may be *set* anywhere in this workflow, in any job, not
    only the one this issue added. Matches a YAML `env:` key (`PYTHONUTF8:`)
    or a shell assignment (`PYTHONUTF8=`), not the variable's name mentioned
    in prose (this file's own explanatory comment names both, deliberately).
    """
    text = _ci_text()

    for variable in ("PYTHONUTF8", "PYTHONIOENCODING"):
        assert not re.search(rf"{variable}\s*[:=]", text), (
            f"{variable} is set in ci.yml -- CF-23.02's 'no forced UTF-8 "
            "workaround required' claim no longer holds, and this must be "
            "either removed or the claim corrected in the same change"
        )
