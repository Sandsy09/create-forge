"""The console objects and encoding hardening every command shares.

ADR 0060 decision 1: kept in its own module, referenced module-qualified
(`_output.console`, `_output.err`) by every other `commands/*` module and by
`cli.py` itself, rather than imported by name -- so a test patching one of
these has exactly one attribute to target regardless of which command it is
exercising.
"""

from __future__ import annotations

import contextlib
import sys

from rich.console import Console

console = Console()
err = Console(stderr=True)


def _harden_console_encoding() -> None:
    r"""Make `console`/`err` degrade unencodable text instead of raising.

    Rich resolves `sys.stdout`/`sys.stderr` fresh on every print (`Console.file`
    is a property, not a frozen reference at construction), and on Windows,
    whenever the process is not attached to a real console -- a pipe, a
    redirect, a test harness -- `GetConsoleMode` fails exactly as it would on
    an unsupported terminal, so Rich takes its "legacy Windows" path and writes
    through the stream's own `.write`, which is `sys.stdout`/`sys.stderr`'s
    default `errors="strict"`. A project name, path, or diagnostic outside the
    console's codepage (a CJK path segment on a `cp1252` host, say) then raises
    `UnicodeEncodeError` -- observed reaching the user *after* `new` had
    already written and committed the project, which is a correctness bug, not
    a cosmetic one (CF-23.02, ADR 0057). `backslashreplace` keeps every such
    character visible (`\\uXXXX`) rather than losing the message, matching
    Click's own choice for `CliRunner`'s stderr stream. Called at the top of
    every invocation (`main()`, Typer's group callback) because CliRunner and
    other harnesses swap `sys.stdout`/`sys.stderr` per call, after this module
    is imported once -- reconfiguring at import time would hardcode whatever
    stream was current then and miss every later swap.

    Never touches path bytes, generated content, or what argument reaches a
    subprocess -- console text only, and only when the stream supports
    `reconfigure` (every real Windows console script and Click's own test
    streams do; anything else is left as it was).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(AttributeError, OSError, ValueError):
            reconfigure(errors="backslashreplace")
