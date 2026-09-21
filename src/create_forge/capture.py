"""The one place subprocess output is captured, and the rules for decoding it.

CF-23.01 (ADR 0055; canonical `docs/subprocess-output.md`). `subprocess.run(...,
text=True)` decodes with the *host locale* -- `cp1252` on a default Windows
install -- so what a child writes and how this process reads it were only ever
lined up by accident. `git` and `uv` write UTF-8; a Python child writes the
locale encoding when piped. On a non-UTF-8 host a single undecodable byte in a
child's stderr raised inside `subprocess.run` and left `stdout` as `None`.
`PYTHONUTF8=1` hides that; it does not define what the bytes are.

So nothing in this package captures text. `run_captured` returns **bytes**, and a
caller decodes only what it genuinely reads, with one of three explicit rules:

- **Diagnostic** (`decode_diagnostic`): UTF-8, `errors="replace"`. For a fact
  extracted from human-oriented output (a version token, whether a value is
  set). It never raises, and its result is never shown raw: raw argv, stdout and
  stderr are never echoed (ADR 0044/0045/0046), because they can carry a
  credential.
- **Protocol** (`decode_protocol`, `parse_protocol_json`): UTF-8, **strict**.
  Machine-readable output either parses or is rejected. Malformed bytes, a byte
  order mark, or a body that is not JSON raise `ProtocolDecodeError`; they can
  never quietly become valid protocol data.
- **Path or binary data**: bytes are left alone (`git merge-file`'s content), or
  are turned into a path with `decode_path`, which is `os.fsdecode`: exactly the
  filesystem's own round trip, with **no replacement character**. Replacing
  bytes in a path would name a different file.

Most call sites read only the return code and so decode nothing at all.

Deliberately engine-free, like `staging.py`, `lifecycle.py`, `update.py` and
`engine_source.py`: nothing here imports `forge_template`
(`tests/test_engine_contract.py`'s `_SHIPPED_MODULES` guard covers it), and
`tests/test_subprocess_policy.py` fails if any other module in this package calls
`subprocess.run`/`Popen`/`check_output`, or asks `subprocess` to decode.

`OSError` (a missing or unlaunchable executable) and `subprocess.TimeoutExpired`
propagate unchanged, so each caller keeps translating them into its own safe
error, and return codes -- including the negative "killed by signal" codes on
POSIX -- reach the caller exactly as `subprocess.run` reports them.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path


class ProtocolDecodeError(ValueError):
    """Protocol output that is not valid UTF-8 JSON.

    Carries no output bytes: what a misbehaving child wrote is never forwarded.
    """


@dataclass(frozen=True, slots=True)
class Captured:
    """One finished child process: its status and its raw, undecoded streams."""

    returncode: int
    stdout: bytes
    stderr: bytes


def run_captured(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: bytes | None = None,
    timeout: float | None = None,
) -> Captured:
    """Run `argv` without a shell and return its status and raw bytes.

    Never passes `text=`, `encoding=` or `universal_newlines`, so nothing is
    decoded and no newline is translated. `stdin`, when given, must already be
    bytes: the caller states the encoding it sends. Never raises for a non-zero
    exit (`check=False`); `OSError` and `subprocess.TimeoutExpired` propagate.
    """
    result = subprocess.run(  # noqa: S603 - callers pass reviewed argv, never a shell
        list(argv),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        input=stdin,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    return Captured(result.returncode, result.stdout, result.stderr)


def decode_diagnostic(data: bytes) -> str:
    """Decode human-oriented output as UTF-8, replacing what is not.

    For extracting a fact, never for showing the output: see the module
    docstring's rule on echoing raw process output.
    """
    return data.decode("utf-8", errors="replace")


def decode_protocol(data: bytes) -> str:
    """Decode machine-readable output as strict UTF-8.

    Raises:
        ProtocolDecodeError: `data` is not valid UTF-8.
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        msg = "protocol output is not valid UTF-8"
        raise ProtocolDecodeError(msg) from exc


def parse_protocol_json(data: bytes) -> object:
    """Parse machine-readable output: strict UTF-8, then strict JSON.

    A byte order mark is left in place by the decode and refused by the parser,
    so it is rejected rather than skipped.

    Raises:
        ProtocolDecodeError: `data` is not valid UTF-8, or is not JSON.
    """
    text = decode_protocol(data)
    try:
        return json.loads(text)
    except (ValueError, RecursionError) as exc:
        msg = "protocol output is not valid JSON"
        raise ProtocolDecodeError(msg) from exc


def decode_path(data: bytes) -> str:
    """Turn path bytes a child printed into a path, with no replacement.

    `os.fsdecode` is the filesystem's own encoding on every host (UTF-8 on
    Windows since Python 3.6, the locale with `surrogateescape` on POSIX), so the
    result names the file the child meant and round-trips through
    `os.fsencode`.
    """
    return os.fsdecode(data)


def display_safe(text: str) -> str:
    r"""Make `text` printable without raising, without changing what it names.

    A path decoded with `decode_path` can hold lone surrogates (bytes the
    filesystem encoding could not decode); printing one raises. They are shown as
    a visible `\udcXX` instead. The original string is untouched: use this only
    at the point of display.
    """
    return text.encode("utf-8", errors="backslashreplace").decode("utf-8")
