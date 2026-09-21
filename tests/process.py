"""Test-side subprocess capture with an explicit encoding (CF-23.01, ADR 0055).

`subprocess.run(..., text=True)` decodes a child's output with the *host locale*.
On a non-UTF-8 Windows host one undecodable byte in a child's stderr raised in
`subprocess`'s reader thread and left `stdout`/`stderr` as `None`, so a test
failed on `None.splitlines()` far from the cause. Children disagree about
encodings -- `git` and `uv` write UTF-8, a Python child writes the locale
encoding when piped -- so no ambient choice is right for all of them.

`run_text` captures **bytes** and decodes them with an encoding the caller can
name, replacing what it cannot read, so a decode can never raise. The default is
UTF-8. A test that deliberately runs a child under a non-UTF-8 setting passes
`encoding=` for what that child writes (CF-23.02 does this with
`locale.getpreferredencoding(False)` when it runs `PYTHONUTF8=0`).

Newlines are translated exactly as `text=True` did (`\\r\\n` and `\\r` become
`\\n`), so existing assertions on captured output are unchanged.

`tests/test_subprocess_policy.py` fails any other text-mode capture in `tests/`
that does not name its encoding.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

DEFAULT_ENCODING = "utf-8"


def _translate_newlines(text: str) -> str:
    """The universal-newlines translation `text=True` applies to captured output."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def run_text(  # noqa: PLR0913 - one keyword per `subprocess.run` option the tests use
    argv: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    stdin: str | None = None,
    check: bool = False,
    encoding: str = DEFAULT_ENCODING,
) -> subprocess.CompletedProcess[str]:
    """Run `argv`, capture both streams as bytes, and decode them explicitly.

    Never raises for a non-zero exit unless `check=True`, and then raises
    `subprocess.CalledProcessError` carrying the decoded output. A timeout raises
    `subprocess.TimeoutExpired`, as `subprocess.run` does. `stdin`, when given, is
    encoded with `encoding`.
    """
    raw = subprocess.run(  # noqa: S603 - reviewed argv in every caller, no shell
        list(argv),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        input=stdin.encode(encoding) if stdin is not None else None,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    stdout = _translate_newlines(raw.stdout.decode(encoding, errors="replace"))
    stderr = _translate_newlines(raw.stderr.decode(encoding, errors="replace"))
    completed = subprocess.CompletedProcess(raw.args, raw.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed
