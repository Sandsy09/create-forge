"""`tests/process.py::run_text` (CF-23.01, ADR 0055): the harness's explicit-decode
capture.

Real children writing bytes with no valid reading. The point is what the helper
promises every test that uses it: a decode never raises, an encoding can be named,
and captured output reads exactly as `text=True` used to.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.process import run_text

UNDECODABLE = b"\xff\xfe\x81\x8d\x8f\x90\x9d"


def _child(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_undecodable_output_is_replaced_not_raised() -> None:
    result = run_text(
        _child(
            "import sys;"
            f"sys.stdout.buffer.write({UNDECODABLE!r});"
            f"sys.stderr.buffer.write({UNDECODABLE!r})"
        )
    )

    assert result.returncode == 0
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)
    assert result.stdout.count("�") == len(UNDECODABLE)


def test_the_default_encoding_is_utf8() -> None:
    result = run_text(
        _child(
            "import sys;"
            "sys.stdout.buffer.write('caf\\u00e9 \\u9879\\u76ee'.encode('utf-8'))"
        )
    )

    assert result.stdout == "café 项目"


def test_a_child_that_writes_another_encoding_is_read_when_it_is_named() -> None:
    """What CF-23.02 does for a deliberate non-UTF-8 child."""
    result = run_text(
        _child("import sys; sys.stdout.buffer.write('caf\\u00e9'.encode('cp1252'))"),
        encoding="cp1252",
    )

    assert result.stdout == "café"


def test_newlines_are_translated_as_text_mode_did() -> None:
    result = run_text(_child("import sys; sys.stdout.buffer.write(b'a\\r\\nb\\rc\\n')"))

    assert result.stdout == "a\nb\nc\n"


def test_stdin_is_encoded_with_the_named_encoding() -> None:
    result = run_text(
        _child("import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"),
        stdin="café",
        encoding="utf-8",
    )

    assert result.stdout == "café"


def test_a_non_zero_exit_does_not_raise_by_default() -> None:
    assert run_text(_child("import sys; sys.exit(3)")).returncode == 3


def test_check_raises_with_the_decoded_output() -> None:
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        run_text(
            _child("import sys; sys.stderr.write('boom'); sys.exit(2)"), check=True
        )

    assert excinfo.value.returncode == 2
    assert excinfo.value.stderr == "boom"


def test_a_timeout_raises_as_subprocess_run_does() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        run_text(_child("import time; time.sleep(30)"), timeout=0.3)
