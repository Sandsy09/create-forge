"""CF-23.01 (ADR 0055): the subprocess capture policy cannot regress silently.

Two rules, checked by parsing source rather than by reading it:

- **Production** (`src/create_forge/`): `capture.py` is the only module that spawns
  a process, and it never asks `subprocess` to decode. Everywhere else calls
  `capture.run_captured` and decodes by an explicit rule
  (`docs/subprocess-output.md`).
- **Tests** (`tests/`): a call that captures in *text mode* must say which
  encoding it means. Bytes capture is always fine. `text=True` alone is the shape
  that decoded with the host locale and failed under a non-UTF-8 Windows console;
  `PYTHONUTF8=1` hid it without defining anything.

The checks are exercised against synthetic snippets first, so a guard that has
quietly stopped matching anything fails here rather than passing for the wrong
reason.

No network, no filesystem outside this repository.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "create_forge"
TESTS = REPO_ROOT / "tests"

_SPAWNERS = frozenset({"run", "Popen", "check_output", "check_call", "call"})
_DECODING_KEYWORDS = frozenset({"text", "universal_newlines", "encoding", "errors"})
_TEXT_MODE_KEYWORDS = frozenset({"text", "universal_newlines"})


def _spawner_calls(source: str) -> list[ast.Call]:
    """Every call that spawns a process through `subprocess`, by either import
    style: `subprocess.run(...)` or `from subprocess import run; run(...)`.
    """
    tree = ast.parse(source)
    bare = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess"
        for alias in node.names
        if alias.name in _SPAWNERS
    }
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _SPAWNERS
            and isinstance(func.value, ast.Name)
            and func.value.id == "subprocess"
        ) or (isinstance(func, ast.Name) and func.id in bare):
            calls.append(node)
    return calls


def _keywords(call: ast.Call) -> dict[str, ast.expr]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}


def _is_true(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def production_violations(source: str) -> list[str]:
    """Any process spawned at all (used for every module except `capture.py`)."""
    return [f"line {call.lineno}: spawns a process" for call in _spawner_calls(source)]


def capture_violations(source: str) -> list[str]:
    """Any decoding requested of `subprocess` (used for `capture.py`)."""
    found: list[str] = []
    for call in _spawner_calls(source):
        asked = sorted(_DECODING_KEYWORDS & _keywords(call).keys())
        if asked:
            found.append(f"line {call.lineno}: passes {', '.join(asked)}")
    return found


def text_mode_violations(source: str) -> list[str]:
    """A text-mode capture with no explicit `encoding=`."""
    found: list[str] = []
    for call in _spawner_calls(source):
        keywords = _keywords(call)
        text_mode = any(_is_true(keywords.get(name)) for name in _TEXT_MODE_KEYWORDS)
        if text_mode and "encoding" not in keywords:
            found.append(f"line {call.lineno}: text mode without an explicit encoding")
    return found


# --------------------------------------------------------------------------- #
# the checks themselves, on synthetic source                                   #
# --------------------------------------------------------------------------- #


def test_the_detector_sees_both_import_styles() -> None:
    qualified = "import subprocess\nsubprocess.run(['git'], text=True)\n"
    bare = "from subprocess import run\nrun(['git'], text=True)\n"
    aliased = "from subprocess import check_output as co\nco(['git'])\n"

    assert len(_spawner_calls(qualified)) == 1
    assert len(_spawner_calls(bare)) == 1
    assert len(_spawner_calls(aliased)) == 1


def test_the_detector_ignores_names_that_are_not_subprocess_calls() -> None:
    source = (
        "import subprocess\n"
        "def run(x): ...\n"
        "run(1)\n"
        "other.run(2)\n"
        "subprocess.CompletedProcess([], 0)\n"
        "subprocess.TimeoutExpired\n"
    )

    assert _spawner_calls(source) == []


def test_the_production_rule_flags_any_spawn() -> None:
    assert production_violations("import subprocess\nsubprocess.run(['x'])\n")
    assert not production_violations("import subprocess\nsubprocess.TimeoutExpired\n")


def test_the_capture_rule_flags_every_decoding_keyword() -> None:
    for keyword in (
        "text=True",
        "universal_newlines=True",
        "encoding='utf-8'",
        "errors='replace'",
    ):
        source = f"import subprocess\nsubprocess.run(['x'], {keyword})\n"
        assert capture_violations(source), keyword
    assert not capture_violations(
        "import subprocess\nsubprocess.run(['x'], capture_output=True, check=False)\n"
    )


def test_the_tests_rule_requires_an_encoding_for_text_mode() -> None:
    bad = "import subprocess\nsubprocess.run(['x'], capture_output=True, text=True)\n"
    also_bad = "import subprocess\nsubprocess.run(['x'], universal_newlines=True)\n"
    explicit = (
        "import subprocess\n"
        "subprocess.run(['x'], text=True, encoding='utf-8', errors='replace')\n"
    )
    bytes_only = "import subprocess\nsubprocess.run(['x'], capture_output=True)\n"
    not_text = "import subprocess\nsubprocess.run(['x'], text=False)\n"

    assert text_mode_violations(bad)
    assert text_mode_violations(also_bad)
    assert not text_mode_violations(explicit)
    assert not text_mode_violations(bytes_only)
    assert not text_mode_violations(not_text)


# --------------------------------------------------------------------------- #
# the rules, on the real tree                                                  #
# --------------------------------------------------------------------------- #


def _production_modules() -> list[Path]:
    return sorted(SRC.glob("*.py"))


def test_capture_is_the_only_production_module_that_spawns_a_process() -> None:
    offenders = {
        path.name: production_violations(path.read_text(encoding="utf-8"))
        for path in _production_modules()
        if path.name != "capture.py"
    }

    assert not {name: found for name, found in offenders.items() if found}, (
        "only create_forge/capture.py may spawn a process (CF-23.01, ADR 0055): "
        "call capture.run_captured and decode by an explicit rule. "
        f"Offenders: { {n: f for n, f in offenders.items() if f} }"
    )


def test_capture_itself_never_asks_subprocess_to_decode() -> None:
    source = (SRC / "capture.py").read_text(encoding="utf-8")

    assert _spawner_calls(source), "capture.py should be where the one spawn lives"
    assert capture_violations(source) == []


def test_no_test_captures_text_without_an_explicit_encoding() -> None:
    offenders = {
        path.name: text_mode_violations(path.read_text(encoding="utf-8"))
        for path in sorted(TESTS.glob("*.py"))
        if path.name != Path(__file__).name
    }

    bad = {name: found for name, found in offenders.items() if found}
    assert not bad, (
        "a text-mode subprocess capture in tests/ must pass an explicit encoding= "
        "(or capture bytes): text=True alone decodes with the host locale and fails "
        "under a non-UTF-8 Windows console (CF-23.01). Use tests/process.py's "
        f"run_text. Offenders: {bad}"
    )
