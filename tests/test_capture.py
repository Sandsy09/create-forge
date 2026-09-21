"""`create_forge.capture` (CF-23.01, ADR 0055): capture as bytes, decode by rule.

Real child processes, no network. The children write exactly the bytes that used
to break `text=True` on a non-UTF-8 Windows host: bytes with no valid UTF-8
reading, and bytes `cp1252` has no character for (`0x81`, `0x8D`, `0x8F`, `0x90`,
`0x9D`). None of these tests depends on the host locale, so they run
identically on Linux and Windows.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from create_forge.capture import (
    Captured,
    ProtocolDecodeError,
    decode_diagnostic,
    decode_path,
    decode_protocol,
    display_safe,
    parse_protocol_json,
    run_captured,
)

# Bytes that are not UTF-8, and that cp1252 cannot decode either.
UNDECODABLE = b"\xff\xfe\x81\x8d\x8f\x90\x9d"


def _child(code: str) -> list[str]:
    return [sys.executable, "-c", code]


# --------------------------------------------------------------------------- #
# run_captured: bytes in, bytes out, nothing decoded                           #
# --------------------------------------------------------------------------- #


def test_run_captured_returns_the_raw_bytes_of_both_streams() -> None:
    result = run_captured(
        _child(
            "import sys;"
            "sys.stdout.buffer.write(b'out \\xff\\x81\\x8f');"
            "sys.stderr.buffer.write(b'err \\x9d\\x8d')"
        )
    )

    assert result == Captured(0, b"out \xff\x81\x8f", b"err \x9d\x8d")


def test_run_captured_translates_no_newlines() -> None:
    result = run_captured(
        _child("import sys; sys.stdout.buffer.write(b'a\\r\\nb\\nc\\r')")
    )

    assert result.stdout == b"a\r\nb\nc\r"


def test_run_captured_passes_stdin_bytes_through_untouched() -> None:
    payload = b"\xff\x00\xfe caf\xc3\xa9 \r\n"

    result = run_captured(
        _child("import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"),
        stdin=payload,
    )

    assert result.stdout == payload


def test_run_captured_reports_the_exit_status_without_raising() -> None:
    result = run_captured(_child("import sys; sys.exit(7)"))

    assert result.returncode == 7


def test_run_captured_honours_cwd_and_env(tmp_path: Path) -> None:
    result = run_captured(
        _child(
            "import os, sys; sys.stdout.write(os.getcwd() + '|' + os.environ['PROBE'])"
        ),
        cwd=tmp_path,
        env={**os.environ, "PROBE": "value"},
    )

    assert result.stdout.decode().split("|")[1] == "value"
    assert Path(result.stdout.decode().split("|")[0]).samefile(tmp_path)


def test_run_captured_lets_a_timeout_propagate() -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        run_captured(_child("import time; time.sleep(30)"), timeout=0.3)


def test_run_captured_lets_a_missing_executable_propagate() -> None:
    with pytest.raises(OSError):
        run_captured(["definitely-not-a-real-executable-cf-23-01"])


def test_run_captured_never_asks_subprocess_to_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The policy in one assertion: no `text`, `encoding`, `errors` or
    `universal_newlines` ever reaches `subprocess.run`.
    """
    seen: dict[str, Any] = {}

    def _fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr("create_forge.capture.subprocess.run", _fake_run)

    run_captured(["git", "status"], stdin=b"x", timeout=5)

    assert not {"text", "encoding", "errors", "universal_newlines"} & seen.keys()
    assert seen["capture_output"] is True
    assert seen["check"] is False
    assert seen["input"] == b"x"


# --------------------------------------------------------------------------- #
# diagnostic policy: lenient, never raises                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("value", range(256))
def test_a_diagnostic_decode_never_raises_for_any_single_byte(value: int) -> None:
    assert isinstance(decode_diagnostic(bytes([value])), str)


def test_a_diagnostic_decode_replaces_only_what_is_not_utf8() -> None:
    text = decode_diagnostic(b"caf\xc3\xa9 \xff ok")

    assert text == "café � ok"


def test_a_diagnostic_decode_handles_bytes_cp1252_cannot() -> None:
    assert decode_diagnostic(UNDECODABLE).count("�") == len(UNDECODABLE)


# --------------------------------------------------------------------------- #
# protocol policy: strict UTF-8, strict JSON                                   #
# --------------------------------------------------------------------------- #


def test_a_protocol_decode_accepts_valid_utf8_including_non_ascii() -> None:
    assert decode_protocol("café → 项目".encode()) == ("café → 项目")


@pytest.mark.parametrize(
    "data",
    [b"\xff", b"caf\xe9", b"ok \xc3", UNDECODABLE],
    ids=["lone-0xff", "latin-1-eacute", "truncated-sequence", "cp1252-holes"],
)
def test_a_protocol_decode_rejects_malformed_bytes(data: bytes) -> None:
    with pytest.raises(ProtocolDecodeError, match="not valid UTF-8"):
        decode_protocol(data)


def test_a_protocol_error_carries_no_output_bytes() -> None:
    with pytest.raises(ProtocolDecodeError) as excinfo:
        decode_protocol(b"secret-token-\xff")

    assert "secret-token" not in str(excinfo.value)


def test_a_protocol_body_parses_to_its_json_value() -> None:
    assert parse_protocol_json(b'{"ok": true, "n": [1, 2]}') == {
        "ok": True,
        "n": [1, 2],
    }


def test_a_protocol_body_with_non_ascii_survives_both_encodings_of_it() -> None:
    raw = '{"name": "café"}'.encode()
    escaped = b'{"name": "caf\\u00e9"}'

    assert parse_protocol_json(raw) == parse_protocol_json(escaped) == {"name": "café"}


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"   ",
        b"not json",
        b'{"ok": tru',
        b'\xef\xbb\xbf{"ok": true}',  # a UTF-8 byte order mark is refused, not skipped
        b'{"ok": "\xff"}',  # valid JSON shape, invalid UTF-8
        b"[" * 5_000,  # nested past the parser's limit
    ],
    ids=["empty", "blank", "text", "truncated", "bom", "bad-utf8-in-json", "too-deep"],
)
def test_a_protocol_body_that_is_not_strict_json_is_rejected(data: bytes) -> None:
    with pytest.raises(ProtocolDecodeError):
        parse_protocol_json(data)


# --------------------------------------------------------------------------- #
# path / binary policy: no replacement                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "name",
    ["plain", "café", "项目", "with space", "snowman-☃"],
)
def test_a_non_ascii_path_round_trips_through_decode_path(name: str) -> None:
    encoded = os.fsencode(name)

    assert decode_path(encoded) == name
    assert os.fsencode(decode_path(encoded)) == encoded


@pytest.mark.skipif(os.name == "nt", reason="undecodable path bytes are a POSIX case")
def test_undecodable_path_bytes_round_trip_instead_of_being_replaced() -> None:
    raw = b"/srv/repo-\xff\xfe"

    decoded = decode_path(raw)

    assert "�" not in decoded  # no replacement character: it names the same file
    assert os.fsencode(decoded) == raw


# --------------------------------------------------------------------------- #
# display_safe                                                                 #
# --------------------------------------------------------------------------- #


def test_display_safe_makes_a_surrogate_path_printable() -> None:
    unprintable = "/srv/repo-\udcff"
    with pytest.raises(UnicodeEncodeError):
        unprintable.encode("utf-8")

    shown = display_safe(unprintable)

    assert shown == "/srv/repo-\\udcff"
    shown.encode("utf-8")  # must not raise


@pytest.mark.parametrize("text", ["plain", "café", "项目 → ☃", ""])
def test_display_safe_leaves_ordinary_text_unchanged(text: str) -> None:
    assert display_safe(text) == text


def test_display_safe_is_idempotent() -> None:
    once = display_safe("a\udc80b")

    assert display_safe(once) == once
