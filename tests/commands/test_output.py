"""`commands/_output.py` -- console encoding hardening (CF-23.02, ADR 0057).

Unit-level: these patch `sys.stdout`/`sys.stderr` directly and call
`_harden_console_encoding()`/`console.print` themselves, rather than going
through `CliRunner`. `test_cli.py::test_every_invocation_hardens_console_
encoding_first` proves the *call site* (`main()` invokes this before any
subcommand runs); these prove the *effect*.
"""

from __future__ import annotations

import sys
from io import BytesIO, TextIOWrapper

import pytest

from create_forge.commands import _output as output_module


def test_harden_console_encoding_relaxes_stdout_and_stderr_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = TextIOWrapper(BytesIO(), encoding="cp1252")
    err_stream = TextIOWrapper(BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err_stream)

    output_module._harden_console_encoding()

    assert out.errors == "backslashreplace"
    assert err_stream.errors == "backslashreplace"


def test_harden_console_encoding_tolerates_a_stream_without_reconfigure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stream some other tool substituted (no `.reconfigure`, unlike every
    real console script and Click's own test streams) is left exactly as it
    was -- never a new failure mode of its own."""

    class _NoReconfigure:
        def write(self, _text: str) -> int:
            return 0

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stdout", _NoReconfigure())
    monkeypatch.setattr(sys, "stderr", _NoReconfigure())

    output_module._harden_console_encoding()  # must not raise


def test_an_unencodable_character_raises_before_the_fix_is_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Establishes the regression `_harden_console_encoding` closes: printing
    text outside the stream's codepage, with the stream's own default
    `errors="strict"`, is exactly what CF-23.02 found reaching the user after
    `new` had already written and committed the project.
    """
    bad_stdout = TextIOWrapper(BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", bad_stdout)

    with pytest.raises(UnicodeEncodeError):
        output_module.console.print("项目")


def test_the_console_degrades_a_character_its_stdout_cannot_encode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_stdout = TextIOWrapper(BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", bad_stdout)
    output_module._harden_console_encoding()

    output_module.console.print("项目")  # must not raise

    bad_stdout.flush()
    assert b"\\u9879\\u76ee" in bad_stdout.buffer.getvalue()
